#!/usr/bin/env bash
# Open kubectl port-forwards for EVERY SQL database in db-targets.tsv (or a subset) so the local DBeaver
# cockpit can reach them all at once. Prints the local-port table and tears every forward down on Ctrl-C.
#
# Usage:   scripts/db/db-forward-all.sh [grep-filter]
# Example: scripts/db/db-forward-all.sh            # every target
#          scripts/db/db-forward-all.sh prod       # only rows whose line matches "prod"
#          scripts/db/db-forward-all.sh ktayl      # only ktayl-* targets
#
# Context via KCTX (default minicloud-oidc; use KCTX=default on the controller). Local ports come from
# db-targets.tsv — the single source of truth shared with gen-dbeaver-sources.py. Backgrounds one
# `kubectl port-forward` per target; a single Ctrl-C kills the whole group.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS="${HERE}/db-targets.tsv"
KCTX="${KCTX:-minicloud-oidc}"
FILTER="${1:-}"
pids=()
cleanup() { echo; echo "closing ${#pids[@]} forwards…" >&2; kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM

printf '%-7s %-22s %-28s %-10s %-5s %s\n' PORT NAMESPACE SERVICE ENGINE ENV LABEL >&2
while IFS=$'\t' read -r lport ns svc rport engine env label secret; do
  [[ "$lport" =~ ^#|^$ ]] && continue
  [[ -n "$FILTER" ]] && ! grep -qi "$FILTER" <<<"$lport $ns $svc $engine $env $label" && continue
  kubectl --context "$KCTX" -n "$ns" port-forward "svc/${svc}" "${lport}:${rport}" >/dev/null 2>&1 &
  pids+=($!)
  printf '%-7s %-22s %-28s %-10s %-5s %s\n' "$lport" "$ns" "$svc" "$engine" "$env" "$label" >&2
done < "$TARGETS"

echo >&2
echo "${#pids[@]} forwards up on localhost. Connect DBeaver to localhost:<PORT>. Ctrl-C to close all." >&2
wait
