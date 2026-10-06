#!/usr/bin/env bash
# generate-erd.sh — reverse-engineer a LIVE database into a Mermaid ER diagram with tbls.
#
# WHAT: connects to a running Postgres or MySQL/MariaDB database (over a kubectl port-forward),
#       introspects its tables + columns + foreign keys, and emits a Mermaid `erDiagram` to stdout.
#       This is the "schema docs from reality" generator — the output is committed to a repo's
#       docs/data-model/ (rendered by Docusaurus), so diagrams can't drift from the real schema.
#
# WHERE IT RUNS: the controller (has kubectl + internet + can port-forward to any ClusterIP DB).
#       Installs tbls to ~/.local/bin on first run (pinned to the latest release at install time).
#
# NO SECRETS BAKED: the DB password is read from the named Kubernetes Secret at runtime.
#
# USAGE (env-parameterized so every DB reuses it):
#   NS=<namespace> SVC=<svc-or-pod> DBPORT=<db-port> LPORT=<local-port> \
#   ENGINE=postgres|mysql DB=<dbname> USER=<dbuser> \
#   SECRET=<k8s-secret> PWKEY=<password-key-in-secret> [SSL=require|disable] \
#   bash generate-erd.sh > <repo>/docs/data-model/<db>.mmd
#
# EXAMPLES:
#   # BookStack (adopted MariaDB)
#   NS=intranet SVC=bookstack-mariadb DBPORT=3306 LPORT=13306 ENGINE=mysql \
#     DB=bookstack USER=bookstack SECRET=bookstack-app-secret PWKEY=DB_PASSWORD bash generate-erd.sh
#   # A CNPG Postgres (app role)
#   NS=langfuse SVC=langfuse-postgres-rw DBPORT=5432 LPORT=15432 ENGINE=postgres \
#     DB=langfuse USER=langfuse SECRET=langfuse-cnpg-role PWKEY=password SSL=require bash generate-erd.sh
#
# For a SVC that is headless (ClusterIP None) or to target a pod, pass SVC=pod/<pod-name>.
# Richer output (per-table Markdown pages + schema spec + `tbls diff` drift-check) = run `tbls doc`
# / `tbls diff` with the same DSN; wire those into each repo's CI as the automated follow-up.
set -euo pipefail

: "${NS:?}" "${SVC:?}" "${DBPORT:?}" "${LPORT:?}" "${ENGINE:?}" "${DB:?}" "${USER:?}" "${SECRET:?}" "${PWKEY:?}"
TBLS="${HOME}/.local/bin/tbls"

# install tbls once (latest linux_amd64 release)
if [ ! -x "$TBLS" ]; then
  mkdir -p "${HOME}/.local/bin"
  url=$(curl -sSL https://api.github.com/repos/k1LoW/tbls/releases/latest \
    | python3 -c 'import sys,json;a=json.load(sys.stdin)["assets"];print(next(x["browser_download_url"] for x in a if "linux_amd64" in x["name"] and x["name"].endswith(".tar.gz")))')
  curl -sSL "$url" | tar xz -C /tmp tbls
  mv /tmp/tbls "$TBLS" && chmod +x "$TBLS"
fi

PASS=$(kubectl get secret "$SECRET" -n "$NS" -o jsonpath="{.data['$PWKEY']}" | base64 -d)

# port-forward (svc/ prefix added unless SVC already carries a kind like pod/)
target="$SVC"; case "$SVC" in */*) : ;; *) target="svc/$SVC" ;; esac
kubectl port-forward -n "$NS" "$target" "${LPORT}:${DBPORT}" >"/tmp/pf-${LPORT}.log" 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null' EXIT
for _ in $(seq 1 20); do (exec 3<>"/dev/tcp/127.0.0.1/${LPORT}") 2>/dev/null && { exec 3>&-; break; }; sleep 1; done

if [ "$ENGINE" = postgres ]; then
  DSN="postgres://${USER}:${PASS}@localhost:${LPORT}/${DB}?sslmode=${SSL:-require}"
else
  DSN="mysql://${USER}:${PASS}@localhost:${LPORT}/${DB}"
fi
exec "$TBLS" out -t mermaid "$DSN"
