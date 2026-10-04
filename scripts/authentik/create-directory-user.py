# pyright: reportMissingImports=false
"""
Provision (idempotently) an Authentik directory USER — so identity ORIGINATES in the IdP (the single
source of truth), and every downstream app (ERPNext, etc.) maps to it via OIDC/email rather than
inventing a local account. This is the manual stand-in for the JML Joiner→Authentik provisioning that
ktayl-iam v3 (S016) will automate; use it to back a synthetic/seed employee with a real SSO identity.

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected). Authentik's REST API 403s tokens on 2026.5.3, so the ORM
is the path. SSO-only (no usable password); optionally joins a group.

Inputs (environment variables):
  AK_USERNAME   required  the login username (on this platform = the 6-digit matricule, e.g. "100002")
  AK_EMAIL      required  the email claim OIDC emits → the key downstream apps match on
  AK_NAME       optional  display name (defaults to the username)
  AK_GROUP      optional  a group name to add the user to (get_or_create the membership)

Output (stdout): CREATED/EXISTS + pk + email; DONE=1.

Example: AK_USERNAME=100002 AK_EMAIL=100002@ktayl.local AK_NAME="Marie Leclerc" \
         bash create-directory-user.sh 100002 100002@ktayl.local "Marie Leclerc"
"""
import os

from authentik.core.models import Group, User

username = os.environ["AK_USERNAME"]
email = os.environ["AK_EMAIL"]
name = os.environ.get("AK_NAME") or username
group = os.environ.get("AK_GROUP", "").strip()

u = User.objects.filter(username=username).first()
if u:
    print(f"EXISTS user={username} pk={u.pk} email={u.email}")
else:
    u = User.objects.create(username=username, email=email, name=name, is_active=True)
    u.set_unusable_password()  # SSO-only — no local password
    u.save()
    print(f"CREATED user={username} pk={u.pk} email={email}")

if group:
    g = Group.objects.filter(name=group).first()
    if g and not g.users.filter(pk=u.pk).exists():
        g.users.add(u)
        print(f"  + added to group {group}")

print("DONE=1")
