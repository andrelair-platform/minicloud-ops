#!/usr/bin/env python3
"""Generate a DBeaver-importable data-sources.json from db-targets.tsv (the single source of truth).

What it does
  - one DBeaver connection per SQL target, pointing at localhost:<localport> (the port-forward opened by
    db-forward-all.sh), foldered by env (Production / Development).
  - env=prod  -> connection-type "prod" (DBeaver renders the tab/header RED) + read-only by default.
  - resolves the real database NAME from each target's k8s Secret (the dbname/database key) so the
    connection lands on the right DB. It reads ONLY the dbname key — never the password (passwords are
    pulled per-session into DBeaver's master-password store; save-password=false here).

Why no passwords: a connection file in git must carry zero secret material (guard-write + house rule).

Usage:   KCTX=minicloud-oidc scripts/db/gen-dbeaver-sources.py > dbeaver-data-sources.json
         (on the controller: KCTX=default …). Then in DBeaver: File -> Import -> DBeaver -> Project /
         connections, pick this file. Verify one dev + one prod connect before relying on it.
"""
import base64
import json
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
TARGETS = HERE / "db-targets.tsv"
KCTX = os.environ.get("KCTX", "minicloud-oidc")

# DBeaver provider/driver ids per engine + the JDBC url template.
ENGINES = {
    "postgres":   ("postgresql", "postgres-jdbc", "jdbc:postgresql://localhost:{port}/{db}"),
    "mariadb":    ("mysql",      "mariaDB",       "jdbc:mariadb://localhost:{port}/{db}"),
    "clickhouse": ("clickhouse", "clickhouse_com","jdbc:clickhouse://localhost:{port}/{db}"),
}
# per-engine fallback DB name when the secret has no dbname key
DEFAULT_DB = {"postgres": "postgres", "mariadb": "", "clickhouse": "default"}
# secret keys that commonly hold the database name (checked in order)
DBNAME_KEYS = ["dbname", "database", "DB_NAME", "POSTGRES_DB",
               "MARIADB_DATABASE", "MYSQL_DATABASE", "CLICKHOUSE_DB"]
# secret keys that hold a full connection DSN (parse its path for the db name)
URL_KEYS = ["database-url", "DATABASE_URL", "db-url"]
# Explicit dbname overrides keyed by namespace — for servers whose secret's dbname key is WRONG or absent
# (verified against the live DB). authentik's -app secret reports `postgres` but its 215 tables are in
# `authentik`; the plain-STS dev servers store no dbname in their secret. Multi-DB servers (ai = 6 app DBs,
# backstage = 13 per-plugin DBs) are deliberately LEFT on the default so the user navigates the DB tree.
DBNAME_OVERRIDE = {
    "authentik": "authentik",
    "ktayl-iam": "ktayl_iam",      # the dev StatefulSet (prod ns is ktayl-iam-prod, resolves from -app)
    "temporal": "temporal",
    "retrieva-dev": "retrieva",
}


def resolve_dbname(ns: str, secret: str, engine: str) -> str:
    """Resolve the connect DB name. Priority: explicit override > DSN path > secret dbname key > default.
    Reads ONLY the dbname/DSN (never the password). Falls back safely on any error."""
    if ns in DBNAME_OVERRIDE:
        return DBNAME_OVERRIDE[ns]
    try:
        out = subprocess.run(
            ["kubectl", "--context", KCTX, "-n", ns, "get", "secret", secret, "-o", "json"],
            capture_output=True, text=True, timeout=15, check=True).stdout
        data = {k: base64.b64decode(v).decode() for k, v in json.loads(out).get("data", {}).items()}
        for key in URL_KEYS:                       # a DSN carries the real db in its path
            if data.get(key):
                from urllib.parse import urlparse
                db = urlparse(data[key]).path.lstrip("/")
                if db:
                    return db
        for key in DBNAME_KEYS:
            if data.get(key):
                return data[key].strip()
    except Exception:
        pass
    return DEFAULT_DB[engine]


# connection-type definitions (DBeaver renders by the type's colour; prod = red + confirm prompts).
CONNECTION_TYPES = {
    "dev": {"name": "Development", "color": "255,255,255", "description": "dev namespaces — regenerable",
            "auto-commit": True, "confirm-execute": False, "confirm-data-change": False},
    "prod": {"name": "Production", "color": "247,211,215", "colorDark": "100,30,35",
             "description": "PROD data — red + read-only by default",
             "auto-commit": False, "confirm-execute": True, "confirm-data-change": True},
}


def main() -> None:
    folders = {"Production": {"description": "PROD data — red + read-only by default"},
               "Development": {"description": "dev namespaces — regenerable"}}
    connections = {}
    for raw in TARGETS.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lport, ns, svc, _rport, engine, env, label, secret = raw.split("\t")
        del _rport  # remote port is used by the forward scripts, not here
        provider, driver, url_tmpl = ENGINES[engine]
        db = resolve_dbname(ns, secret, engine)
        is_prod = env == "prod"
        conf: dict[str, object] = {
            "host": "localhost", "port": lport, "database": db,
            "url": url_tmpl.format(port=lport, db=db),
            "configurationType": "MANUAL",
            "type": "prod" if is_prod else "dev",   # DBeaver reads the connection-type from here
            "auth-model": "native",
        }
        if engine == "postgres":
            conf["provider-properties"] = {"postgresql.show.all.databases": "true"}
        connections[f"{engine}-{ns}-{svc}"] = {
            "provider": provider, "driver": driver,
            "name": label, "description": f"{ns}/{svc} via localhost:{lport} (port-forward)",
            "save-password": False, "read-only": is_prod,
            "folder": "Production" if is_prod else "Development",
            "configuration": conf,
        }
    print(json.dumps({"folders": folders, "connections": connections,
                      "connection-types": CONNECTION_TYPES}, indent=2))


if __name__ == "__main__":
    main()
