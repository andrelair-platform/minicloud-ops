# sdlc_loop — SDLC closing-the-loop detector (AI-native Play 13)

Turns a **production control-band breach** into a re-entry artifact for the AI-native SDLC
loop. Detection + escalation are **100% deterministic** (no model, no cost); the *diagnosis*
is a human running Claude Code on the resulting `intent.md` (on-plan, not metered/headless).

```
Prometheus (via apiserver proxy) → control-chart z-score vs rolling baseline → tier
   1σ → log     2σ → write intent.md     3σ → write intent.md + open GitHub issue
                                    → human runs Claude Code on the intent.md → fix flows
                                      through the normal chain (plan.md → PR → review → Kargo)
```

## Layout
| File | Role |
|---|---|
| `control_chart.py` | pure z-score + tier math (unit-tested, no I/O) |
| `prometheus.py` | queries Prometheus off-cluster via `kubectl get --raw …/proxy/…` (no SSO/token) |
| `artifact.py` | renders the `intent.md`; optionally opens a GitHub issue |
| `main.py` | orchestrator entry (`minicloud-sdlc-loop`) |
| `bands.json` | the control bands (metric, PromQL, direction) + baseline window + tiers |

## Config (`bands.json`)
Each band: `name`, `query` (PromQL that aggregates to one series), `direction`
(`high` = alert on a rise, `low` = alert on a drop, `both`). Baseline = a rolling
`window`/`step` range; a value beyond 1/2/3σ (in the bad direction) escalates.
Seed bands: `pod_restarts_1h`, `ingress_5xx_rate`, `nodes_ready`, `rollout_failures`
(reliability / DORA change-failure) + `open_p1_items` (delivery-flow, from the ghproj-exporter).

## Run
```bash
minicloud-sdlc-loop --dry-run     # one pass, never opens issues
minicloud-sdlc-loop               # one pass; opens an issue on 3σ IF a token is present
python3 -m sdlc_loop.main --dry-run    # from the repo root
PYTHONPATH=. python3 tests/test_control_chart.py   # deterministic unit tests
```
Installed as an hourly systemd timer by `install.sh`. Intents land in
`~/minicloud-ops-intents/`; logs go to journald.

## GitHub issue (optional, token-gated)
Tier-3 opens an issue only if a **scoped** token exists at `~/.sdlc-loop-github-token`
(a fine-grained PAT with **issues:write** on `andrelair-platform/minicloud-gitops`) or
`$SDLC_LOOP_GH_TOKEN`. Without it, the loop still logs + writes `intent.md` — the core loop
is credential-free by design.

## Safety
- The detector **only observes** — it never mutates the cluster; any fix goes through the
  normal PR/CODEOWNERS/Kargo path.
- It always exits 0 (a detector must not fail its own timer); errors are logged.
- Fully-autonomous headless diagnosis (a metered model call in the timer) is deliberately
  NOT wired — diagnosis stays a human-triggered, on-plan Claude Code step.
