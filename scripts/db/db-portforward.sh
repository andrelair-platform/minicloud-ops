#!/usr/bin/env bash
# Open ONE kubectl port-forward to an in-cluster database so a LOCAL client (DBeaver) can reach it.
# The DBs are ClusterIP-only (no public exposure) — a port-forward is the sanctioned tunnel; access is
# bounded by your own kubeconfig RBAC (zero cluster footprint, unlike the retired in-cluster Adminer).
#
# Usage:   scripts/db/db-portforward.sh <namespace> <service> <localport> [remoteport]
# Example: scripts/db/db-portforward.sh ktayl-core-prod ktayl-core-cnpg-rw 55438 5432
#          scripts/db/db-portforward.sh erp erpnext-mariadb-sts 53306 3306
#
# Context: defaults to KCTX (env) or `minicloud-oidc` (the Mac daily-use OIDC context). On the controller
# run with  KCTX=default  (its single context). CNPG HA clusters: always target the <cluster>-rw service
# (it follows the primary across a failover) — never a pod or the -ro/-r read service.
set -euo pipefail
NS="${1:?namespace required}"; SVC="${2:?service required}"; LPORT="${3:?local port required}"
RPORT="${4:-5432}"; KCTX="${KCTX:-minicloud-oidc}"
echo "port-forward  ${NS}/${SVC}  ->  localhost:${LPORT}  (remote ${RPORT}, context ${KCTX})" >&2
echo "  Ctrl-C to close." >&2
exec kubectl --context "$KCTX" -n "$NS" port-forward "svc/${SVC}" "${LPORT}:${RPORT}"
