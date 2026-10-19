#!/usr/bin/env bash
# Configure (idempotently) a GLPI LDAP directory pointing at the shared Authentik LDAP outpost, so
# employees are imported/synced as GLPI users (ticket requesters).
#
# WHY a PHP-in-pod approach (not raw SQL like configure-sso-provider.sh): GLPI stores the bind
# password (glpi_authldaps.rootdn_passwd) ENCRYPTED with the instance key (/var/glpi/config/
# glpicrypt.key). A plain SQL insert would store an un-decryptable value and the bind would fail.
# So we drive GLPI's own AuthLDAP::add()/update() (via inc/includes.php) which encrypts it correctly.
# The bind secret is piped via stdin -> `read` -> env -> getenv(); it never appears in any argv.
#
# Matching / dedup design (see the ktayl-itsm as-built doc):
#   login_field = cn   -> glpi_users.name = the Authentik username (matricule 100001.. / demo.*)
#   email1_field = mail-> glpi_useremails is populated so the OIDC singlesignon plugin (which keys on
#                         email) links an SSO login to the SAME imported account (no duplicate).
#   condition  = (&(objectClass=user)(memberOf=cn=Workplace Users,ou=groups,<basedn>))
#                -> only real employees; excludes service accounts / the shared `it` mailbox / akadmin.
#
# RUN ON THE CONTROLLER. Requires: kubectl (GLPI ns), ~/.vault-ops-token, ~/minicloud-ca.crt.
# Idempotent: matches the directory row by name; updates in place if it already exists.
#
# Usage: configure-ldap-directory.sh <ns> <directory-name> <vault-kv-path> [host] [basedn] [filter]
# Example:
#   configure-ldap-directory.sh itsm "Authentik (ktayl employees)" platform/authentik-ldap-outpost
set -euo pipefail
umask 077

NS="${1:?namespace required (e.g. itsm)}"
DNAME="${2:?directory display-name required}"
KVPATH="${3:?vault kv path required (e.g. platform/authentik-ldap-outpost)}"
HOST="${4:-ktayl-ldap-outpost.authentik.svc.cluster.local}"
BASEDN="${5:-dc=devandre,dc=sbs}"
FILTER="${6:-(&(objectClass=user)(memberOf=cn=Workplace Users,ou=groups,dc=devandre,dc=sbs))}"
PORT="${LDAP_PORT:-3389}"

V=https://vault.10.0.0.200.nip.io
CA="$HOME/minicloud-ca.crt"
OPS="$(cat "$HOME/.vault-ops-token")"

# 1. read the bind DN + secret from Vault (ops token = read-only on platform/*). Not echoed.
RESP=$(curl -sk --cacert "$CA" -H "X-Vault-Token: $OPS" "$V/v1/secret/data/$KVPATH")
BINDDN=$(printf '%s' "$RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["data"]["stalwart-bind-dn"])')
BINDPW=$(printf '%s' "$RESP" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["data"]["stalwart-bind-secret"])')
[ -n "$BINDDN" ] && [ -n "$BINDPW" ] || { echo "ERROR: Vault $KVPATH missing stalwart-bind-dn/stalwart-bind-secret"; exit 1; }

# 2. locate the GLPI pod
GPOD=$(kubectl get pods -n "$NS" -l app=glpi -o jsonpath='{.items[0].metadata.name}')
[ -n "$GPOD" ] || { echo "ERROR: no glpi pod in ns $NS"; exit 1; }

# 3. write the PHP provisioner into the pod (non-secret: DN/host/basedn/filter come from env;
#    the password is read from stdin inside the container, so it is never on an argv).
kubectl exec -i "$GPOD" -n "$NS" -c glpi -- sh -c 'cat > /tmp/glpi_ldap_cfg.php' <<'PHP'
<?php
chdir('/var/www/glpi');
define('GLPI_ROOT', getcwd());
include GLPI_ROOT.'/inc/includes.php';

$name   = getenv('LDAP_NAME');
$host   = getenv('LDAP_HOST');
$port   = (int) getenv('LDAP_PORT');
$basedn = getenv('LDAP_BASEDN');
$rootdn = getenv('LDAP_BINDDN');
$pass   = getenv('LDAP_BINDPW');   // plaintext; GLPI encrypts it on add/update
$cond   = getenv('LDAP_FILTER');

$fields = [
    'name'           => $name,
    'host'           => $host,
    'port'           => $port,
    'basedn'         => $basedn,
    'rootdn'         => $rootdn,
    'rootdn_passwd'  => $pass,
    'condition'      => $cond,
    'login_field'    => 'cn',
    'sync_field'     => '',
    'email1_field'   => 'mail',
    'realname_field' => 'sn',
    'firstname_field'=> 'givenname',
    'use_bind'       => 1,
    'use_dn'         => 1,
    'use_tls'        => 0,
    'is_active'      => 1,
    'is_default'     => 1,
    'comment'        => 'Managed by minicloud-ops/scripts/glpi/configure-ldap-directory.sh',
];

$ldap = new AuthLDAP();
$existing = $ldap->find(['name' => $name]);
if (count($existing)) {
    $row = reset($existing);
    $fields['id'] = (int) $row['id'];
    $ldap->update($fields);
    echo "UPDATED authldap id=".$fields['id']."\n";
} else {
    $id = $ldap->add($fields);
    echo "CREATED authldap id=".$id."\n";
}

// connection smoke test (binds with the stored, re-decrypted credential)
$srv = new AuthLDAP();
$srv->getFromDB($fields['id'] ?? $id);
$conn = $srv->connect();
echo "bind_test=".($conn ? "OK" : "FAILED")."\n";
PHP

# 4. run it: pipe the secret on stdin -> read into env -> php getenv(). Secret stays off every argv.
printf '%s' "$BINDPW" | kubectl exec -i "$GPOD" -n "$NS" -c glpi -- \
  env LDAP_NAME="$DNAME" LDAP_HOST="$HOST" LDAP_PORT="$PORT" LDAP_BASEDN="$BASEDN" \
      LDAP_BINDDN="$BINDDN" LDAP_FILTER="$FILTER" \
  sh -c 'read -r LDAP_BINDPW; export LDAP_BINDPW; php /tmp/glpi_ldap_cfg.php; rm -f /tmp/glpi_ldap_cfg.php'

echo "directory='$DNAME' host=$HOST:$PORT basedn=$BASEDN"
echo "filter=$FILTER"
