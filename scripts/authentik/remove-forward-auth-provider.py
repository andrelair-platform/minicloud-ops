# pyright: reportMissingImports=false
"""
remove-forward-auth-provider.py — idempotently DELETE an Authentik forward-auth (proxy) Application +
its ProxyProvider + group PolicyBinding, and detach the provider from the embedded outpost. The exact
reverse of forward-auth-provider.py — the decommission counterpart (used when an SSO'd app is retired).

RUNS INSIDE the authentik server pod via `ak shell`:
    kubectl exec -n authentik deploy/authentik-server -i -- ak shell < remove-forward-auth-provider.py
Override the target by prepending `NAME=...; SLUG=...` when piping (defaults below = the retired adminer).

Safe to re-run: each step no-ops if the object is already gone. Only touches the named provider/app —
the shared embedded outpost and every other provider are untouched.
"""
from authentik.core.models import Application
from authentik.providers.proxy.models import ProxyProvider
from authentik.outposts.models import Outpost

NAME = globals().get("NAME", "adminer-forward-auth")
SLUG = globals().get("SLUG", "adminer")

provider = ProxyProvider.objects.filter(name=NAME).first()
app = Application.objects.filter(slug=SLUG).first()

# detach from the embedded outpost first (so deleting the provider doesn't dangle a reference)
detached = False
if provider:
    out = Outpost.objects.filter(name__icontains="embedded").first()
    if out and provider.pk in out.providers.values_list("pk", flat=True):
        out.providers.remove(provider)
        detached = True

# PolicyBindings cascade-delete with the Application; delete the app, then the provider
app_deleted = False
if app:
    app.delete()  # cascades its PolicyBindings
    app_deleted = True

prov_deleted = False
if provider:
    provider.delete()
    prov_deleted = True

print(f"outpost_detach={'yes' if detached else 'n/a'} "
      f"app={'deleted' if app_deleted else 'absent'} "
      f"provider={'deleted' if prov_deleted else 'absent'}")
