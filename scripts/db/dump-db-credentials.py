#!/usr/bin/env python3
"""Write ONE offline credentials file for every database in db-targets.tsv (host/port/db/user/password).

    KCTX=minicloud-oidc ./dump-db-credentials.py [output-path]
    # default output: ~/Documents/minicloud-db-credentials.txt

⚠️  SENSITIVE OUTPUT. The file it writes contains PLAINTEXT passwords for the whole platform. It is created
    chmod 600. NEVER commit it, never sync it to cloud storage, delete it once imported into DBeaver. This
    SCRIPT holds no secrets — it reads them from the live k8s Secrets at runtime and only prints a redacted
    summary (counts; never a password value).

Resolution per database (same logic as gen-dbeaver-sources.py so the file matches the DBeaver connections):
  - username/password: tried against common key names; a `database-url` DSN is parsed if present.
  - database name: explicit ns override > DSN path > secret dbname key > engine default.
  - MULTI-DB servers (one Postgres hosting many app DBs) are emitted with the superuser login + the full
    database list, because there is no single "right" DB to pin (ai = 6 tools, backstage = 13 plugin DBs).
"""
import base64, json, os, pathlib, subprocess, sys
from urllib.parse import urlparse, unquote

KCTX = os.environ.get("KCTX", "minicloud-oidc")
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.home() / "Documents" / "minicloud-db-credentials.txt"
HERE = pathlib.Path(__file__).resolve().parent
TARGETS = HERE / "db-targets.tsv"

PW_KEYS = ["password", "postgres-password", "PGPASSWORD", "pgpass", "POSTGRES_PASSWORD", "DB_PASSWORD",
           "mariadb-password", "mariadb-root-password", "MARIADB_PASSWORD", "MYSQL_PASSWORD", "db-password",
           "clickhouse-password", "CLICKHOUSE_PASSWORD", "DSN_PASSWORD"]
USER_KEYS = ["username", "postgres-username", "POSTGRES_USER", "DB_USER", "mariadb-user", "MARIADB_USER",
             "MYSQL_USER", "db-username", "user", "CLICKHOUSE_USER", "PGUSER", "DSN_LOGIN"]
DB_KEYS = ["dbname", "database", "DB_NAME", "POSTGRES_DB", "MARIADB_DATABASE", "MYSQL_DATABASE", "CLICKHOUSE_DB"]
URL_KEYS = ["database-url", "DATABASE_URL", "db-url"]
# the connect-DB the app actually uses, where the secret's dbname is wrong/absent (verified live)
DBNAME_OVERRIDE = {"authentik": "authentik", "ktayl-iam": "ktayl_iam", "temporal": "temporal", "retrieva-dev": "retrieva"}
# one Postgres server hosting many app DBs -> superuser login + the full list (no single DB to pin)
MULTIDB = {
    "ai": ["flowise", "litellm", "mlflow", "openwebui", "ragdb", "vaultwarden"],
    "backstage": ["backstage_plugin_catalog", "backstage_plugin_scaffolder", "backstage_plugin_techdocs",
                  "backstage_plugin_auth", "backstage_plugin_permission", "backstage_plugin_search",
                  "backstage_plugin_kubernetes", "backstage_plugin_notifications", "backstage_plugin_signals",
                  "backstage_plugin_mcp-actions", "backstage_plugin_app", "backstage_plugin_proxy", "backstage_plugin_argocd"],
}


def get_secret(ns, name):
    r = subprocess.run(["kubectl", "--context", KCTX, "-n", ns, "get", "secret", name, "-o", "json"],
                       capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        return None
    out = {}
    for k, v in json.loads(r.stdout).get("data", {}).items():
        try:
            out[k] = base64.b64decode(v).decode()
        except Exception:
            out[k] = "<binary>"
    return out


def pick(d, keys):
    for k in keys:
        if d.get(k):
            return d[k]
    return None


def main():
    import datetime
    rows = [r.split("\t") for r in TARGETS.read_text().splitlines() if r.strip() and not r.lstrip().startswith("#")]
    blocks, have_pw = [], 0
    for lport, ns, svc, rport, engine, env, label, secret in rows:
        d = get_secret(ns, secret) or {}
        b = [f"[{label}]  ({env.upper()})", "  engine:   " + engine,
             f"  host:     localhost      # kubectl -n {ns} port-forward svc/{svc} {lport}:{rport}",
             f"  port:     {lport}", f"  in-cluster-host: {svc}.{ns}.svc.cluster.local:{rport}"]
        if ns in MULTIDB:                                   # multi-DB server -> superuser + db list
            pw = d.get("postgres-password") or pick(d, PW_KEYS)
            dbs = MULTIDB[ns]
            b += ["  username: postgres        # superuser — SAME login reaches every database below",
                  "  password: " + (pw or "<ERROR reading postgres-password>"),
                  f"  databases ({len(dbs)} — set DBeaver 'Database' to ONE of these):",
                  *[f"    - {x}" for x in dbs]]
            have_pw += 1 if pw else 0
        else:
            pw, usr, db = pick(d, PW_KEYS), pick(d, USER_KEYS), DBNAME_OVERRIDE.get(ns) or pick(d, DB_KEYS)
            url = pick(d, URL_KEYS)
            if url and (not pw or not usr or not db):       # parse a DSN for anything missing
                try:
                    u = urlparse(url)
                    pw = pw or (unquote(u.password) if u.password else None)
                    usr = usr or (unquote(u.username) if u.username else None)
                    db = db or (u.path.lstrip("/") or None)
                except Exception:
                    pass
            if not usr and engine == "clickhouse":
                usr = "default"
            b += [f"  database: {db or '(any — leave blank to list all)'}",
                  f"  username: {usr or '(check app env)'}",
                  "  password: " + (pw or "<no recognised password key in %s/%s>" % (ns, secret))]
            have_pw += 1 if pw else 0
        blocks.append("\n".join(b))

    hdr = (f"# minicloud — database credentials (prod + dev)\n"
           f"# generated {datetime.date.today()} — PRIVATE, chmod 600, do NOT commit.\n"
           f"# Open each via: minicloud-ops/scripts/db/db-forward-all.sh  then connect to localhost:<port>.\n"
           f"# {len(rows)} databases | with password: {have_pw}\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(hdr + "\n" + "\n\n".join(blocks) + "\n")
    os.chmod(OUT, 0o600)
    print(f"WROTE {OUT}  (perms {oct(OUT.stat().st_mode)[-3:]}, {OUT.stat().st_size} bytes)")
    print(f"  {len(rows)} databases | with password: {have_pw}  (no credential values printed)")


if __name__ == "__main__":
    main()
