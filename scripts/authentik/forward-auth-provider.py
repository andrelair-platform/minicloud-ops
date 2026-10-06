# pyright: reportMissingImports=false
"""
forward-auth-provider.py — idempotently create an Authentik **forward-auth** (proxy) Application for an
app that has NO native OIDC, gated to a group, and attach it to the embedded outpost.

RUNS INSIDE the authentik server pod via `ak shell`:
    kubectl exec -n authentik deploy/authentik-server -i -- ak shell < forward-auth-provider.py
(or pipe with env-style vars prepended). Parameterized via the UPPERCASE constants below — edit or
override by prepending `NAME=...; HOST=...; GROUP=...` assignments when piping.

What it creates (get_or_create — safe to re-run):
  - a ProxyProvider in forward_single mode for https://<HOST>
  - an Application (slug) bound to that provider
  - a PolicyBinding so ONLY members of <GROUP> may access (non-members → 403)
  - adds the provider to the embedded outpost (so ingress forward-auth works)

Mirror of the homer-eng / temporal-forward-auth pattern (see homer-eng ingress + homer-rbac-spec.md).
The matching ingress carries the standard goauthentik.io auth_request snippets (see the app's Ingress).
"""
from authentik.core.models import Application, Group
from authentik.flows.models import Flow, FlowDesignation
from authentik.providers.proxy.models import ProxyProvider, ProxyMode
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding

# ---- parameters (override by prepending NAME=... etc. when piping) ----
NAME  = globals().get("NAME",  "adminer-forward-auth")
SLUG  = globals().get("SLUG",  "adminer")
HOST  = globals().get("HOST",  "https://adminer.10.0.0.200.nip.io")
GROUP = globals().get("GROUP", "Platform Admins")

authz = Flow.objects.filter(designation=FlowDesignation.AUTHORIZATION,
                            slug="default-provider-authorization-implicit-consent").first() \
        or Flow.objects.filter(designation=FlowDesignation.AUTHORIZATION).first()
invalidation = Flow.objects.filter(slug="default-provider-invalidation-flow").first() \
        or Flow.objects.filter(designation=FlowDesignation.INVALIDATION).first()

provider, pc = ProxyProvider.objects.get_or_create(
    name=NAME,
    defaults=dict(authorization_flow=authz, mode=ProxyMode.FORWARD_SINGLE, external_host=HOST),
)
changed = pc
# ensure correct mode/host/flows on re-run
if provider.mode != ProxyMode.FORWARD_SINGLE: provider.mode = ProxyMode.FORWARD_SINGLE; changed = True
if provider.external_host != HOST:            provider.external_host = HOST; changed = True
if provider.authorization_flow_id != (authz.pk if authz else None): provider.authorization_flow = authz; changed = True
if invalidation and provider.invalidation_flow_id != invalidation.pk: provider.invalidation_flow = invalidation; changed = True
if changed: provider.save()

app, ac = Application.objects.get_or_create(slug=SLUG, defaults=dict(name=SLUG, provider=provider))
if app.provider_id != provider.pk:
    app.provider = provider; app.save()

# group gate — only <GROUP> members may access
grp = Group.objects.filter(name=GROUP).first()
if not grp:
    raise SystemExit(f"GROUP {GROUP!r} not found in Authentik")
pb, bc = PolicyBinding.objects.get_or_create(target=app, group=grp, defaults=dict(order=0, enabled=True))

# attach provider to the embedded outpost
out = Outpost.objects.filter(name__icontains="embedded").first()
added = False
if out and provider.pk not in out.providers.values_list("pk", flat=True):
    out.providers.add(provider); added = True

print(f"provider={'created' if pc else 'exists'}/{'updated' if changed and not pc else 'ok'} "
      f"app={'created' if ac else 'exists'} group_binding={'created' if bc else 'exists'}({GROUP}) "
      f"outpost={'added' if added else ('present' if out else 'MISSING')}")
