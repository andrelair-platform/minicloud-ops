# pyright: reportMissingImports=false
"""
Grant an Authentik SERVICE ACCOUNT a least-privilege set of global permissions (ORM).

RUNS INSIDE the authentik pod via `ak shell`. Authentik's REST API 403s tokens on 2026.5.3, so the
ORM is the path. Used to give a platform service account (e.g. ktayl-iam-svc, the IGA sync engine)
exactly the permissions it needs to manage group membership — and NOTHING more (threat T4):
view_user, view_group, add_group, change_group. No delete, no user mutation, no flows/providers.

Authentik uses its OWN RBAC (authentik_rbac), NOT Django `user_permissions`: global perms attach to
a `Role` (`role.assign_perms('app_label.codename', ...)`), and the Role is bound to a Group the user
belongs to. So this creates (idempotently) a dedicated role + a carrier group, assigns the minimal
perms, and puts the service account in the group.

Inputs (environment variables):
  AK_SVC_USERNAME  required  the service-account username (e.g. "ktayl-iam-svc")
  AK_ROLE_NAME     optional  role name (default "<svc>-group-manager")
  AK_PERMS         optional  comma list of authentik_core codenames
                             (default: view_user,view_group,add_group,change_group)

Output (stdout): the role/group binding + perms + DONE=1.

Example: AK_SVC_USERNAME=ktayl-iam-svc bash grant-service-group-perms.sh ktayl-iam-svc
"""
import os

from authentik.core.models import Group, User
from authentik.rbac.models import Role

username = os.environ["AK_SVC_USERNAME"]
role_name = os.environ.get("AK_ROLE_NAME", f"{username}-group-manager")
codenames = [
    c.strip()
    for c in os.environ.get("AK_PERMS", "view_user,view_group,add_group,change_group").split(",")
    if c.strip()
]
perms = [f"authentik_core.{c}" for c in codenames]

svc = User.objects.get(username=username)
role, _ = Role.objects.get_or_create(name=role_name)
for p in perms:  # Role.assign_perms takes ONE perm per call (perm[, obj])
    role.assign_perms(p)
# a carrier group that holds the role and the service account (Authentik binds roles via groups).
grp, _ = Group.objects.get_or_create(name=f"{role_name}-binding")
grp.roles.add(role)
grp.users.add(svc)
grp.save()

print(f"role={role.name} group={grp.name} user={svc.username}")
for p in perms:
    print("perm:", p)
print("DONE=1")
