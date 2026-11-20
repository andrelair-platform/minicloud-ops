# doc_freshness — "is this doc still true?" detector

A deterministic, weekly check that compares the **concrete live facts a published doc asserts** (node
count, k3s version, ArgoCD app count, PrometheusRule count, Grafana dashboards, Gatekeeper constraints…)
against the **live cluster**, and flags drift. The docs-side twin of [`sdlc_loop`](../sdlc_loop/README.md):
a deterministic detector + a human remediator — **no model is called and no doc is edited** by the check.

## Why
Docs rot silently. A page accurate at merge drifts as the platform grows (e.g. ArgoCD apps 93 → 119,
PrometheusRules 53 → 68). CI can't catch it — the facts live in the cluster, not the repo. This closes the
loop: the cluster is queried off nothing but `kubectl`, and a drifted number becomes a visible report
instead of a stale doc someone trips over in an interview/audit.

## How it works
- `claims.json` — each claim = a fact a doc asserts + the probe that reads it live + how to compare
  (`eq` · `approx` (±tolerance) · `gte` · `lte` · `set_eq`) + the `doc`/`anchor` to fix on drift.
- `probes.py` — small named `kubectl` readers (no shell in the claims file → no injection surface).
- `main.py` — runs every claim, writes a report to `~/minicloud-ops-intents/docs-freshness.md`
  (the dir the owner already watches for `sdlc_loop`), and **exits non-zero on drift** so the systemd
  timer surfaces it. `--dry-run` prints without writing; `--json` for machine output.

## Run it
```bash
minicloud-docs-freshness --dry-run     # one pass, prints the table, writes nothing
minicloud-docs-freshness               # writes the report, exit 1 on drift
cat ~/minicloud-ops-intents/docs-freshness.md
systemctl list-timers minicloud-docs-freshness.timer
journalctl -u minicloud-docs-freshness.service --no-pager | tail
```

## When a claim DRIFTS
Update the doc page/anchor (the `doc`/`anchor` fields point at it) to the live value — or fix the cluster
if the doc states the *intended* state — then bump `expect` in `claims.json` to match, so the check passes
again. Add a new fact by adding a probe to `probes.py` and a claim to `claims.json`.

Cadence: weekly (`minicloud-docs-freshness.timer`, Monday 06:30 UTC). Install via the repo `install.sh`.
