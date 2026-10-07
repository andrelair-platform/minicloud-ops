#!/usr/bin/env bash
# =============================================================================
# stalwart-mail-ops.sh — operate the Stalwart mail server after the Authentik
# LDAP auth cutover (mail logins authenticate against Authentik via LDAP).
#
# Runs on the CONTROLLER (needs kubectl + the Vault break-glass chain). The
# controller is off-cluster and can't reach stalwart.mail.svc directly, so each
# IMAP/SMTP action runs inside a transient, Gatekeeper-compliant pod in ns `mail`.
#
# Credentials are read at runtime from Vault (nothing baked in):
#   secret/platform/stalwart-admin-user   -> username/password (admin, for SMTP submit)
#   secret/platform/ktayl-iam             -> default-mailbox-password (new-joiner default)
# Vault is reached with the ops-token; the admin path needs the root token, which
# is decrypted from ~/.vault-root-token.age via the age identity in Vault
# (secret/platform/k3s-backup-age) — the standard controller break-glass chain.
#
# USAGE:
#   stalwart-mail-ops.sh verify <email> [password]   # IMAP login check (default pw if omitted)
#   stalwart-mail-ops.sh welcome <email>             # send a welcome mail -> auto-creates the mailbox
#   stalwart-mail-ops.sh clear-cache                 # restart Stalwart (clears stale auth/dir cache)
#
# WHY these three (learned 2026-10-07, gitops #1686 / memory project_mail_authentik_ldap_federation):
#   * A brand-new LDAP user has NO Stalwart mailbox until their first delivery — `welcome` guarantees it.
#   * Stalwart CACHES auth/directory results; a login attempted BEFORE the user's password is set gets
#     cached as a failure and keeps failing until the cache clears — `clear-cache` is the fix (this is
#     exactly what blocked sophie.bernard). `verify` confirms a user can actually log in via Authentik.
# =============================================================================
set -uo pipefail

VAULT_ADDR="https://vault.10.0.0.200.nip.io"
CA="${HOME}/minicloud-ca.crt"
NS="mail"
HOST="stalwart.mail.svc.cluster.local"
POD_IMAGE="docker.io/library/python:3.12-slim"

die(){ echo "ERROR: $*" >&2; exit 1; }

vault_root_token(){
  local ops id root
  ops=$(cat "${HOME}/.vault-ops-token") || die "no ~/.vault-ops-token"
  id=$(/usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $ops" \
        "$VAULT_ADDR/v1/secret/data/platform/k3s-backup-age" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['data']['identity'])") || die "cannot read age identity"
  [ -n "$id" ] || die "empty age identity"
  root=$(printf '%s' "$id" | "${HOME}/.local/bin/age" -d -i /dev/stdin "${HOME}/.vault-root-token.age" 2>/dev/null) \
    || die "age decrypt of root token failed"
  [ -n "$root" ] || die "empty root token"
  printf '%s' "$root"
}

vault_get(){ # $1=path  $2=field
  local tok; tok="$1"; shift
  /usr/bin/curl -s --cacert "$CA" -H "X-Vault-Token: $tok" \
    "$VAULT_ADDR/v1/secret/data/$1" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['data']['$2'])"
}

# Run a python snippet inside a throwaway Gatekeeper-compliant pod in ns mail.
# $1 = pod name ; $2 = env block (yaml list items) ; stdin = python source
run_pod(){
  local name="$1" envblock="$2" src; src="$(cat)"
  kubectl delete pod "$name" -n "$NS" --ignore-not-found >/dev/null 2>&1
  # base64 the source so no quoting games
  local b64; b64=$(printf '%s' "$src" | base64 | tr -d '\n')
  cat <<EOF | kubectl apply -f - >/dev/null 2>&1
apiVersion: v1
kind: Pod
metadata: { name: ${name}, namespace: ${NS} }
spec:
  restartPolicy: Never
  securityContext: { runAsNonRoot: true, runAsUser: 1000, fsGroup: 1000, seccompProfile: { type: RuntimeDefault } }
  containers:
    - name: t
      image: ${POD_IMAGE}
      env:
        - { name: HOME, value: /tmp }
        - { name: SRC_B64, value: "${b64}" }
${envblock}
      command: ["sh","-lc"]
      args: ["echo \$SRC_B64 | base64 -d > /tmp/s.py && python /tmp/s.py"]
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities: { drop: ["ALL"] }
      volumeMounts: [{ name: tmp, mountPath: /tmp }]
  volumes: [{ name: tmp, emptyDir: {} }]
EOF
  local i ph
  for i in $(seq 1 30); do
    ph=$(kubectl get pod "$name" -n "$NS" -o jsonpath='{.status.phase}' 2>/dev/null)
    [ "$ph" = Succeeded ] || [ "$ph" = Failed ] && break; sleep 3
  done
  kubectl logs "$name" -n "$NS" 2>/dev/null
  kubectl delete pod "$name" -n "$NS" --ignore-not-found >/dev/null 2>&1
}

cmd="${1:-}"; shift || true
case "$cmd" in
  verify)
    email="${1:-}"; [ -n "$email" ] || die "usage: verify <email> [password]"
    pw="${2:-}"
    if [ -z "$pw" ]; then
      ops=$(cat "${HOME}/.vault-ops-token"); pw=$(vault_get "$ops" platform/ktayl-iam default-mailbox-password) \
        || die "cannot read default-mailbox-password"
    fi
    run_pod imap-verify "        - { name: EMAIL, value: \"$email\" }
        - { name: PW, value: \"$pw\" }" <<'PY'
import imaplib, ssl, os
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
try:
    M=imaplib.IMAP4(os.environ.get("HOST","stalwart.mail.svc.cluster.local"),143); M.starttls(ssl_context=ctx)
    M.login(os.environ["EMAIL"], os.environ["PW"]); M.select("INBOX")
    t,d=M.search(None,"ALL"); print(f"VERIFY ok: {os.environ['EMAIL']} logs in via Authentik | INBOX={len(d[0].split())}")
    M.logout()
except Exception as e:
    print(f"VERIFY FAIL: {os.environ['EMAIL']} -> {e!r}")
PY
    ;;
  welcome)
    to="${1:-}"; [ -n "$to" ] || die "usage: welcome <email>"
    root=$(vault_root_token)
    au=$(vault_get "$root" platform/stalwart-admin-user username)
    ap=$(vault_get "$root" platform/stalwart-admin-user password)
    [ -n "$au" ] && [ -n "$ap" ] || die "cannot read admin creds from Vault"
    run_pod smtp-welcome "        - { name: TO, value: \"$to\" }
        - { name: AU, value: \"$au\" }
        - { name: AP, value: \"$ap\" }" <<'PY'
import smtplib, ssl, os
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
host="stalwart.mail.svc.cluster.local"; to=os.environ["TO"]; au=os.environ["AU"]
try:
    s=smtplib.SMTP(host,587,timeout=25); s.starttls(context=ctx); s.login(au, os.environ["AP"])
    s.sendmail(au,[to], f"From: {au}\r\nTo: {to}\r\nSubject: Bienvenue\r\n\r\nVotre boite mail est active.\r\n")
    s.quit(); print(f"WELCOME ok: delivered to {to} (mailbox auto-created on delivery)")
except Exception as e:
    print(f"WELCOME FAIL: {to} -> {e!r}")
PY
    ;;
  clear-cache)
    echo "Restarting Stalwart to clear the auth/directory cache (~15s mail downtime)..."
    kubectl rollout restart statefulset/stalwart -n "$NS"
    kubectl rollout status statefulset/stalwart -n "$NS" --timeout=120s
    ;;
  *)
    grep -E '^#( |=|!)' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
