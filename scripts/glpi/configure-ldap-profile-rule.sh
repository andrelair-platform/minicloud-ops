#!/usr/bin/env bash
# Configure (idempotently) a GLPI authorization rule (RuleRight) that assigns a GLPI PROFILE to users
# who belong to a given Authentik/LDAP group — i.e. LDAP-group -> GLPI-role mapping.
#
# WHY a PHP-in-pod approach (same reason as configure-ldap-directory.sh): a RuleRight is three linked
# objects (Rule + RuleCriteria + RuleAction) with framework-managed constants (PATTERN_CONTAIN, the
# 'assign' action). We drive GLPI's own classes (via inc/includes.php) so the rule is built correctly
# and is picked up by the rule engine on the next LDAP sync — not hand-crafted SQL across three tables.
#
# The rule uses the per-user `memberof` LDAP attribute (criterion CONTAINS the group DN), so the GLPI
# directory does NOT need group-search configured — the rule engine fetches memberof per user. Users NOT
# matching keep GLPI's default-profile fallback (Self-Service); matching users get the mapped profile.
#
# RUN ON THE CONTROLLER. Requires: kubectl (the GLPI ns). No secrets (all args are non-sensitive).
# Idempotent: matched by rule name — an existing rule of that name is deleted (cascading its
# criteria/actions) and recreated, so re-running converges to exactly the intended rule.
#
# Usage: configure-ldap-profile-rule.sh <ns> <rule-name> <group-dn> <profile-name> [entity-id] [recursive]
# Example:
#   configure-ldap-profile-rule.sh itsm "LDAP: Direction IT / SI -> Technician" \
#       "cn=Direction IT / SI,ou=groups,dc=devandre,dc=sbs" "Technician"
set -euo pipefail
umask 077

NS="${1:?namespace required (e.g. itsm)}"
RULE_NAME="${2:?rule display-name required}"
GROUP_DN="${3:?LDAP group DN required (e.g. cn=Direction IT / SI,ou=groups,dc=devandre,dc=sbs)}"
PROFILE_NAME="${4:?GLPI profile name required (e.g. Technician)}"
ENTITY_ID="${5:-0}"
RECURSIVE="${6:-1}"

GPOD=$(kubectl get pods -n "$NS" -l app=glpi -o jsonpath='{.items[0].metadata.name}')
[ -n "$GPOD" ] || { echo "ERROR: no glpi pod in ns $NS"; exit 1; }

kubectl exec -i "$GPOD" -n "$NS" -c glpi -- sh -c 'cat > /tmp/glpi_profile_rule.php' <<'PHP'
<?php
chdir('/var/www/glpi');
define('GLPI_ROOT', getcwd());
include GLPI_ROOT.'/inc/includes.php';

$ruleName = getenv('RULE_NAME');
$groupDn  = getenv('GROUP_DN');
$profName = getenv('PROFILE_NAME');
$entity   = (int) getenv('ENTITY_ID');
$recur    = (int) getenv('RECURSIVE');

// resolve the profile id by name
$prof = new Profile();
$found = $prof->find(['name' => $profName]);
if (!count($found)) { fwrite(STDERR, "ERROR: profile '$profName' not found\n"); exit(1); }
$pid = (int) reset($found)['id'];

// idempotent: drop an existing rule of this name (cascades criteria + actions), then recreate
$rule = new RuleRight();
foreach ($rule->find(['name' => $ruleName, 'sub_type' => 'RuleRight']) as $row) {
    $rule->delete(['id' => (int) $row['id']]);
}
$rid = $rule->add([
    'name'        => $ruleName,
    'sub_type'    => 'RuleRight',
    'match'       => 'AND',
    'is_active'   => 1,
    'entities_id' => 0,
    'comment'     => 'Managed by minicloud-ops/scripts/glpi/configure-ldap-profile-rule.sh',
]);
if (!$rid) { fwrite(STDERR, "ERROR: failed to create rule\n"); exit(1); }

$crit = new RuleCriteria();
$crit->add([
    'rules_id'  => $rid,
    'criteria'  => 'memberof',
    'condition' => Rule::PATTERN_CONTAIN,
    'pattern'   => $groupDn,
]);

$act = new RuleAction();
$act->add(['rules_id' => $rid, 'action_type' => 'assign', 'field' => 'profiles_id', 'value' => $pid]);
$act->add(['rules_id' => $rid, 'action_type' => 'assign', 'field' => 'entities_id', 'value' => $entity]);
$act->add(['rules_id' => $rid, 'action_type' => 'assign', 'field' => 'is_recursive', 'value' => $recur]);

echo "RULE ok id=$rid  '$ruleName'  memberof CONTAINS '$groupDn'  -> profile '$profName' (id=$pid) entity=$entity recursive=$recur\n";
PHP

kubectl exec -i "$GPOD" -n "$NS" -c glpi -- \
  env RULE_NAME="$RULE_NAME" GROUP_DN="$GROUP_DN" PROFILE_NAME="$PROFILE_NAME" \
      ENTITY_ID="$ENTITY_ID" RECURSIVE="$RECURSIVE" \
  sh -c 'php /tmp/glpi_profile_rule.php; rm -f /tmp/glpi_profile_rule.php'
