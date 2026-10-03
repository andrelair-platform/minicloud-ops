# pyright: reportMissingImports=false
"""
Idempotent Authentik OIDC provider + application bootstrap (ORM).

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected; see .claude/rules/reusable-scripts.md). Authentik's REST API
403s every token on 2026.5.3, so the ORM via `ak shell` is the only working path (docs/identity-two-layer.md).

Inputs (environment variables):
  AK_APP_SLUG       required  the application + provider slug (e.g. "bookstack")
  AK_APP_NAME       required  the application display name (e.g. "BookStack")
  AK_REDIRECT_URIS  required  comma- or newline-separated strict redirect URIs
  AK_ADD_GROUPS     optional  "1" (default) also create/attach a `groups` scope mapping -> groups claim

Output (stdout markers, captured by the caller — never echo the secret elsewhere):
  CLIENTID=<client_id>
  CLIENTSECRET=<client_secret>
  DONE=1

Example (from a host with kubectl):
  bash scripts/authentik/oidc-provider.sh bookstack BookStack https://intranet.devandre.sbs/oidc/callback
"""
import os

from authentik.core.models import Application
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

slug = os.environ["AK_APP_SLUG"]
name = os.environ["AK_APP_NAME"]
redirects = [u.strip() for u in os.environ["AK_REDIRECT_URIS"].replace(",", "\n").splitlines() if u.strip()]
add_groups = os.environ.get("AK_ADD_GROUPS", "1") == "1"
if not redirects:
    raise SystemExit("AK_REDIRECT_URIS is empty")

signing = CertificateKeyPair.objects.filter(name__icontains="self-signed").order_by("name").first()
if signing is None:
    signing = CertificateKeyPair.objects.exclude(key_data="").first()
authz = Flow.objects.get(slug="default-provider-authorization-implicit-consent")

scopes = list(ScopeMapping.objects.filter(scope_name__in=["openid", "email", "profile"]))
if add_groups:
    groups_map, _ = ScopeMapping.objects.get_or_create(
        name=f"{name} groups",
        defaults=dict(
            scope_name="groups",
            description=f"{name}: Authentik groups -> roles",
            expression='return {"groups": [g.name for g in request.user.ak_groups.all()]}',
        ),
    )
    scopes.append(groups_map)

prov, _ = OAuth2Provider.objects.get_or_create(
    name=slug, defaults=dict(authorization_flow=authz, signing_key=signing)
)
prov.authorization_flow = authz
prov.signing_key = signing
prov.client_type = "confidential"  # enum name varies across versions; the stored value is stable
# redirect_uris schema differs across versions: new = list[RedirectURI], old = newline string
try:
    from authentik.providers.oauth2.models import RedirectURI, RedirectURIMatchingMode

    prov.redirect_uris = [RedirectURI(RedirectURIMatchingMode.STRICT, u) for u in redirects]
except Exception:
    prov.redirect_uris = "\n".join(redirects)
prov.save()
prov.property_mappings.set(scopes)
prov.save()

app, _ = Application.objects.get_or_create(slug=slug, defaults=dict(name=name))
app.name = name
app.provider = prov
app.save()

print("CLIENTID=%s" % prov.client_id)
print("CLIENTSECRET=%s" % prov.client_secret)
print("DONE=1")
