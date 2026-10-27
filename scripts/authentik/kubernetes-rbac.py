# pyright: reportMissingImports=false
"""Provision dedicated Kubernetes authorization groups in Authentik.

Runs inside the Authentik server with ``ak shell``. By default this is a
read-only plan. Set ``AK_APPLY=1`` through the wrapper to apply it.
"""
import os

from authentik.core.models import Group, User
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

apply = os.environ.get("AK_APPLY", "0") == "1"

group_sources = {
    "k8s-cluster-admins": ["Direction IT / SI"],
    "k8s-cluster-viewers": ["Direction Cybersécurité", "Direction Audit Interne"],
    "k8s-dev-editors": ["Développeurs"],
}

for target_name, source_names in group_sources.items():
    source_groups = list(Group.objects.filter(name__in=source_names))
    missing = sorted(set(source_names) - {group.name for group in source_groups})
    if missing:
        raise SystemExit(f"missing source groups for {target_name}: {missing}")
    source_users = User.objects.filter(groups__in=source_groups).distinct()
    target = Group.objects.filter(name=target_name).first()
    current = set(target.users.values_list("pk", flat=True)) if target else set()
    desired = set(source_users.values_list("pk", flat=True))
    print(
        f"group {target_name}: sources={source_names} desired={len(desired)} "
        f"current={len(current)} add={len(desired - current)}"
    )
    if apply:
        target, _ = Group.objects.get_or_create(name=target_name)
        target.users.add(*source_users)

admin = Group.objects.filter(name="k8s-cluster-admins").first()
identity = User.objects.get(username="100001")
identity_present = bool(admin and admin.users.filter(pk=identity.pk).exists())
print(f"identity 100001 in k8s-cluster-admins: {identity_present}")
if apply and not identity_present:
    admin = Group.objects.get(name="k8s-cluster-admins")
    admin.users.add(identity)

provider = OAuth2Provider.objects.get(client_id="kubernetes")
attached_ids = set(provider.property_mappings.values_list("pk", flat=True))
custom_profile = ScopeMapping.objects.get(name="OAuth Mapping: OpenID profile")
groups_mapping = ScopeMapping.objects.get(name="kubernetes-groups")
default_profile = ScopeMapping.objects.get(
    name="authentik default OAuth Mapping: OpenID 'profile'"
)
print(
    "provider mappings: "
    f"custom_profile={custom_profile.pk in attached_ids} "
    f"groups={groups_mapping.pk in attached_ids} "
    f"duplicate_default_profile={default_profile.pk in attached_ids}"
)
if apply:
    provider.property_mappings.add(custom_profile, groups_mapping)
    provider.property_mappings.remove(default_profile)

print("APPLIED=1" if apply else "PLAN_ONLY=1")
