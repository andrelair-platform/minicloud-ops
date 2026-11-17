# pyright: reportMissingImports=false
"""
Idempotently bind an Authentik Application (by slug) to a GROUP for ACCESS — i.e. add "members of
<group> may reach this app" to the app's authorization bindings. ADDITIVE: existing bindings are left
untouched (the app's policy engine is `any`, so this grants the new group access alongside the others).

This is the 'who may reach the app at all' layer (access-role-model.md §4 layer 3) — the companion to a
tool's in-app role mapping (Grafana role_attribute_path / ArgoCD policy.csv / Backstage permission.rbac).
Reusable across the platform-access-matrix SSO-gate wave.

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected). Authentik's REST API 403s tokens on 2026.5.3, so the ORM is
the path.

Inputs (environment variables):
  AK_APP_SLUG  required  the Application slug (e.g. "grafana", "argo-cd", "backstage")
  AK_GROUP     required  the group name to grant access (e.g. "ktayl-engineering")

Output (stdout): BOUND/EXISTS + app + group + pk; DONE=1. Non-fatal WARN if the app or group is missing.

Example: bash bind-app-group.sh grafana ktayl-engineering
"""
import os

from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding

slug = os.environ["AK_APP_SLUG"]
group = os.environ["AK_GROUP"]

app = Application.objects.filter(slug=slug).first()
if app is None:
    print(f"WARN app-not-found slug={slug}")
    raise SystemExit(0)
grp = Group.objects.filter(name=group).first()
if grp is None:
    print(f"WARN group-not-found name={group}")
    raise SystemExit(0)

pb, created = PolicyBinding.objects.get_or_create(
    target=app, group=grp, defaults=dict(order=0, enabled=True)
)
print(f"{'BOUND' if created else 'EXISTS'} app={slug} group={group} pk={pb.pk}")
print("DONE=1")
