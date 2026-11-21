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


def resolve_dbname(ns: str, secret: str, engine: str) -> str:
    """Read ONLY the database-name key from the secret (never the password). Fall back on any failure."""
    try:
        out = subprocess.run(
            ["kubectl", "--context", KCTX, "-n", ns, "get", "secret", secret, "-o", "json"],
            capture_output=True, text=True, timeout=15, check=True).stdout
        data = json.loads(out).get("data", {})
        for key in DBNAME_KEYS:
            if key in data:
                return base64.b64decode(data[key]).decode().strip()
    except Exception:
        pass
    return DEFAULT_DB[engine]


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
            "auth-model": "native",
        }
        if engine == "postgres":
            conf["provider-properties"] = {"postgresql.show.all.databases": "true"}
        connections[f"{engine}-{ns}-{svc}"] = {
            "provider": provider, "driver": driver,
            "name": label, "description": f"{ns}/{svc} via localhost:{lport} (port-forward)",
            "save-password": False, "read-only": is_prod,
            "folder": "Production" if is_prod else "Development",
            "connection-type": "prod" if is_prod else "dev",
            "configuration": conf,
        }
    print(json.dumps({"folders": folders, "connections": connections}, indent=2))


if __name__ == "__main__":
    main()
