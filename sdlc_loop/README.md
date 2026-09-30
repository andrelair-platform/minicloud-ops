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

## What is a "band"? (plain-language)

A **band is the normal range for one number, plus a rule to shout when that number leaves
the range.**

**Fever analogy:** your temperature is normally ~37 °C. 36.5–37.5 is fine — that's the normal
*band*. Hit 39 °C and you know something's wrong. Nobody handed you a rule "39 = sick"; you
just know 37 is normal and 39 is far from it. A control band does exactly that for a number
the platform produces.

**A real one — `ingress_5xx_rate`** (server errors/sec): the detector watches it for a week and
learns "normal ≈ 0, barely wiggles." That learned normal zone *is* the band. If errors jump to
5/sec, that's miles outside → flag it.

**Where the word comes from:** picture a chart with the average as a line down the middle and two
more lines above and below it. The strip *between* those lines is the "band" — the zone of normal
values. A dot inside = fine; a dot outside = flagged.

**Why a band instead of a fixed threshold** ("alert if errors > 10")? Every number has a *different*
normal — errors ~0, healthy nodes ~6, open P1s ~40. A fixed threshold means hand-picking (and
re-picking) a magic number per metric. A band **learns each number's own normal automatically**,
so you just say "watch this number" and it works out what "abnormal" means.

**So concretely:** one band = **one number to watch** + which direction is bad (a rise, or a drop).
When a number goes abnormal: a little → **log**; more → **write an `intent.md`**; way off → **open a
GitHub issue**. "Add a band" = watch one more number (one entry in `bands.json`).

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
