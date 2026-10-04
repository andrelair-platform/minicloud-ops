# pyright: reportMissingImports=false
"""
Grant an Authentik SERVICE ACCOUNT a least-privilege set of global permissions (ORM).

RUNS INSIDE the authentik pod via `ak shell`. Authentik's REST API 403s tokens on 2026.5.3, so the
ORM is the path. Used to give a platform service account (e.g. ktayl-iam-svc, the IGA sync engine)
exactly the permissions it needs to manage group membership — and NOTHING more (threat T4):
view_user, view_group, add_group, change_group. No delete, no user mutation, no flows/providers.

Inputs (environment variables):
  AK_SVC_USERNAME  required  the service-account username (e.g. "ktayl-iam-svc")
  AK_PERMS         optional  comma list of authentik_core codenames
                             (default: view_user,view_group,add_group,change_group)

Output (stdout): one GRANTED/HAS line per permission + DONE=1.

Example: AK_SVC_USERNAME=ktayl-iam-svc bash grant-service-group-perms.sh ktayl-iam-svc
"""
import os

from authentik.core.models import User
from django.contrib.auth.models import Permission

username = os.environ["AK_SVC_USERNAME"]
codenames = [
    c.strip()
    for c in os.environ.get("AK_PERMS", "view_user,view_group,add_group,change_group").split(",")
    if c.strip()
]

u = User.objects.get(username=username)
for codename in codenames:
    perm = Permission.objects.get(codename=codename, content_type__app_label="authentik_core")
    if u.user_permissions.filter(pk=perm.pk).exists():
        print(f"HAS authentik_core.{codename}")
    else:
        u.user_permissions.add(perm)
        print(f"GRANTED authentik_core.{codename}")
u.save()
print("DONE=1")
