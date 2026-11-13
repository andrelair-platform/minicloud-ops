# pyright: reportMissingImports=false
"""
Idempotently ensure Authentik groups exist, optionally adding one member to each.

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected; see .claude/rules/reusable-scripts.md). The REST API 403s
every token on this Authentik version, so the ORM via `ak shell` is the working path.

Used to create the per-module authorization groups a service's @PreAuthorize gate checks (e.g. the
ktayl-core module groups `Complaints Handler` / `Finance`), and to seed the operator into them.

Inputs (environment variables):
  AK_GROUPS  required  comma- or newline-separated group names (e.g. "Complaints Handler,Finance")
  AK_MEMBER  optional  a username added to EVERY listed group (warns, does not fail, if not found)

Output (stdout markers):
  GROUP=<name> created=<bool>
  MEMBER_ADDED group=<name> user=<username>   (only when AK_MEMBER is set + found)
  DONE=1

Example (from a host with kubectl — via ensure-groups.sh):
  bash scripts/authentik/ensure-groups.sh "Complaints Handler,Finance" kanmegnea
"""
import os

from authentik.core.models import Group, User

names = [g.strip() for g in os.environ["AK_GROUPS"].replace(",", "\n").splitlines() if g.strip()]
if not names:
    raise SystemExit("AK_GROUPS is empty")
member = os.environ.get("AK_MEMBER", "").strip()

user = None
if member:
    user = User.objects.filter(username=member).first()
    if user is None:
        print("WARN member-not-found=%s" % member)

for name in names:
    group, created = Group.objects.get_or_create(name=name)
    print("GROUP=%s created=%s" % (name, bool(created)))
    if user is not None:
        group.users.add(user)
        print("MEMBER_ADDED group=%s user=%s" % (name, member))

print("DONE=1")
