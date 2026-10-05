# pyright: reportMissingImports=false
"""
Create the `Workplace Users` birthright group and bind it to the birthright workplace apps (ORM).

RUNS INSIDE the authentik pod via `ak shell` (Authentik 2026.5.3 REST API 403s tokens → ORM is the path).

The birthright model (workplace-architecture.md): every employee belongs to ONE all-staff group that
every workplace app is bound to, so a Joiner added to this group instantly gets the whole suite; the
Joiner handler (ktayl-iam) adds each new user to this group. Source of truth for the set = the
Company Portal (homer-config). Apps NOT in the set (platform tools, LOB back-office) stay role-gated.

Safety: this adds a group PolicyBinding to each app. For apps currently open to any-authenticated-user
(groups=[]), that RESTRICTS access to group members — so ALL current active human (internal) users are
added to the group FIRST (no lockout). For apps already bound to Direction groups, the extra binding
BROADENS access to all staff (OR semantics) — the intended birthright effect (e.g. chat for everyone).

Idempotent: get_or_create group, membership, and bindings. Re-runnable.

Inputs (env):
  WP_GROUP   optional  group name (default "Workplace Users")
  WP_APPS    optional  comma list of Application slugs to bind
                       (default: the birthright set present in Authentik)

Example: bash scripts/authentik/workplace-birthright.sh   (wrapper pipes this into ak shell)
"""
import os

from authentik.core.models import Application, Group, User
from authentik.policies.models import PolicyBinding

group_name = os.environ.get("WP_GROUP", "Workplace Users")
default_apps = "nextcloud,open-webui,matrix-synapse,jitsi-meet,vaultwarden,erpnext,plane,bookstack"
app_slugs = [s.strip() for s in (os.environ.get("WP_APPS") or default_apps).split(",") if s.strip()]

grp, created = Group.objects.get_or_create(name=group_name)
print(f"group: {group_name} ({'created' if created else 'exists'})")

# 1. add every active, internal (human) user — never service accounts, never AnonymousUser
added = 0
for u in User.objects.filter(is_active=True):
    if getattr(u, "type", "") != "internal":
        continue
    if u.username == "AnonymousUser":
        continue
    if not grp.users.filter(pk=u.pk).exists():
        grp.users.add(u)
        added += 1
grp.save()
print(f"members: {grp.users.count()} (added {added} this run)")

# 2. bind the group to each birthright app (idempotent)
for slug in app_slugs:
    try:
        app = Application.objects.get(slug=slug)
    except Application.DoesNotExist:
        print(f"  SKIP {slug}: no such application")
        continue
    pb, made = PolicyBinding.objects.get_or_create(
        target=app, group=grp, defaults={"order": 0, "enabled": True}
    )
    print(f"  bind {slug}: {'created' if made else 'exists'}")

print("DONE=1")
