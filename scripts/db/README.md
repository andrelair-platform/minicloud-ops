# Local database cockpit — DBeaver + kubectl port-forward (standalone runbook)

Access every platform database from a **local DBeaver** over `kubectl port-forward`. No AI agent needed —
follow this file top to bottom. (This replaced the retired in-cluster Adminer console.)

Everything here is driven by **`db-targets.tsv`** — the single source of truth (one row per database:
local-port · namespace · service · engine · env · secret · db-name-override). Edit that file to add/retune
a database; the scripts and the connection generator all read it.

---

## 0. Prerequisites (check once)

1. **Tailscale connected** on your Mac, and the **home cluster powered on**. The DBs are private
   (ClusterIP only) — the *only* remote path is a port-forward over Tailscale. It works from anywhere, not
   just home, **as long as Tailscale is up and the cluster is online**.
2. **kubectl context `minicloud-oidc`** exists locally (daily-use OIDC context — there is **no**
   `minicloud` context on the Mac; the controller uses `default`).
3. **Confirm the whole path is up** (if this returns `ok`, DBeaver will work):
   ```bash
   kubectl --context minicloud-oidc get --raw='/healthz'      # -> ok
   ```
   If it hangs/errors: Tailscale is down, the cluster is off, or your OIDC session expired (re-login via
   Authentik: `kubectl --context minicloud-oidc get ns` and follow the browser prompt).
4. **DBeaver Community** installed: `brew install --cask dbeaver-community`.

---

## 1. Open the tunnels

```bash
cd ~/Developer/cloudplateform/minicloud-ops/scripts/db
./db-forward-all.sh                 # opens ALL databases on localhost:<port>; Ctrl-C closes them all
./db-forward-all.sh prod            # or filter: only rows matching "prod"
./db-forward-all.sh ktayl           # or: only ktayl-* targets
```
One database only:
```bash
./db-portforward.sh <namespace> <service> <localport> [remoteport]
# e.g.  ./db-portforward.sh ktayl-core-prod ktayl-core-cnpg-rw 55438 5432
```
Ports: PostgreSQL `554xx`, MariaDB `533xx`, ClickHouse `58123` (see `db-targets.tsv`). On the **controller**
run with `KCTX=default` prefixed; on the Mac the default `minicloud-oidc` is correct.

---

## 2. Load the connections into DBeaver (first time)

```bash
KCTX=minicloud-oidc ./gen-dbeaver-sources.py > ~/Desktop/dbeaver-connections.json
```
Then in DBeaver: **File → Import → DBeaver → Project / connections** → pick the file off the Desktop.

The generated connections: `localhost:<port>`, the **correct database** per server, foldered **Production**
(red + read-only) / **Development**, and **no passwords stored** (you enter them on first connect).

> If the Import wizard complains ("zip END header not found"), it wanted a DBeaver *export archive*. The
> alternative is to merge `dbeaver-connections.json` into DBeaver's workspace file directly:
> `~/Library/DBeaverData/workspace6/General/.dbeaver/data-sources.json` — **quit DBeaver first**, merge the
> `connections`/`folders`/`connection-types` keys, then relaunch.

---

## 3. Get a password when DBeaver prompts

Passwords are never written to the connection file — pull per-session:
```bash
# CNPG clusters (the majority) — the <cluster>-app basic-auth secret:
kubectl --context minicloud-oidc -n <ns> get secret <cluster>-app \
  -o jsonpath='{.data.password}' | base64 -d; echo

# plain/vendor DBs — discover the key first, then read it:
kubectl --context minicloud-oidc -n <ns> get secret <name> \
  -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'
```
Where each credential actually lives (Vault → ESO → the k8s Secret): see the `developer-platform/db-credentials`
docs page + the `db-credentials.md` rule.

**Prefer NOT ticking "save password" on PROD connections** — a stolen-but-locked laptop then can't reach prod.

### Optional: generate one offline credentials file (SENSITIVE)
```bash
KCTX=minicloud-oidc ./dump-db-credentials.py                 # -> ~/Documents/minicloud-db-credentials.txt (chmod 600)
KCTX=minicloud-oidc ./dump-db-credentials.py /path/to/out.txt
```
> ⚠️ The OUTPUT contains plaintext passwords for the whole platform. It is `chmod 600`, **never commit it**,
> never sync it to cloud storage, and delete it once imported. The *script* holds no secrets (reads at runtime).

---

## 4. Daily use + safety

- **Production** connections render **red** and open **read-only** — writing needs a deliberate toggle
  (right-click → Edit Connection → uncheck read-only). Dev stays plain.
- Close tunnels with **Ctrl-C** in the `db-forward-all.sh` terminal.

---

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **DBeaver shows "No tables"** | You're on the empty default `postgres` database. Set the connection's **Database** to the real one (or expand the *Databases* node). The generator already pins the right DB; if you see this, the server is **multi-database** (below). |
| **A server lists many databases** | `ai platform pg` hosts **6** (openwebui/litellm/ragdb/vaultwarden/flowise/mlflow); `backstage` hosts **13** per-plugin DBs. No single "right" one — pick which you want in the **Database** field. Login = superuser `postgres` + the `postgres-password` secret key. |
| **"Navigator node … not found"** on launch | A stale editor tab from a previous database. Dismiss it, re-expand the connection. |
| **Can't connect / tunnel hangs** | Run the `healthz` check (step 0). `ok` = path up; otherwise Tailscale down / cluster off / OIDC expired. |
| **CNPG HA failover** | Always target the `<cluster>-rw` service (the TSV already does) — it follows the primary. |

---

## 6. Files in this directory
| File | Purpose |
|---|---|
| `db-targets.tsv` | **single source of truth** — one row per database |
| `db-portforward.sh` | open ONE tunnel |
| `db-forward-all.sh` | open ALL (or a filtered subset) of the tunnels |
| `gen-dbeaver-sources.py` | emit a DBeaver-importable connection file (correct DB, prod red+read-only, no passwords) |
| `dump-db-credentials.py` | OPTIONAL — one offline `chmod 600` credentials file (sensitive; never commit the output) |

Central docs: `https://andrelair-platform.github.io/minicloud-platform-docs/platform/developer-platform/dbeaver-db-access`
