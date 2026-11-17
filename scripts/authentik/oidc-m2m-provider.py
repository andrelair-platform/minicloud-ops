# pyright: reportMissingImports=false
"""
Idempotent Authentik OAuth2 **M2M (client-credentials)** provider + application bootstrap (ORM).

The machine-to-machine sibling of oidc-provider.py: for a service that calls another service's API with
an OAuth2 `client_credentials` token (no browser, no redirect). The consumer validates the JWT against
the shared Authentik JWKS + an issuer allowlist (e.g. ktayl-core ADR-016). First caller: dms-classifier
→ the ktayl-core policy lookup (task #14).

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected; see .claude/rules/reusable-scripts.md). Authentik's REST API
403s every token on 2026.x, so the ORM via `ak shell` is the only working path.

> VERIFY AT ACTIVATION: mirror the already-working **ktayl-underwriting** M2M provider (the proven
> reference on this cluster). Inspect it first:
>   OAuth2Provider.objects.get(name="ktayl-underwriting") → .grant_types, .issuer_mode, .signing_key
> and match this script's provider to it (esp. issuer_mode, so `iss` == the INTERNAL-host per-app form
> http://authentik-server.authentik.svc:80/application/o/<slug>/ that the consumer allowlists).

Inputs (environment variables):
  AK_APP_SLUG   required  the application + provider slug (e.g. "dms-classifier")
  AK_APP_NAME   required  the application display name (e.g. "DMS Classifier (M2M)")
  AK_ISSUER_MODE optional "per_provider" (default — iss = per-app slug URL, what an allowlist matches)
                          or "global" (iss = the global issuer). per_provider matches ktayl-underwriting.

Output (stdout markers, captured by the caller — never echo the secret elsewhere):
  CLIENTID=<client_id>
  CLIENTSECRET=<client_secret>
  ISSUER=<the iss string the consumer must allowlist>
  DONE=1
"""
import os

from authentik.core.models import Application
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

slug = os.environ["AK_APP_SLUG"]
name = os.environ["AK_APP_NAME"]
issuer_mode = os.environ.get("AK_ISSUER_MODE", "per_provider")

# A confidential client minting via client_credentials still needs an authorization_flow set (Authentik
# requires it on every OAuth2Provider), even though the M2M grant never runs the browser flow.
authz = Flow.objects.get(slug="default-provider-authorization-implicit-consent")
signing = CertificateKeyPair.objects.filter(name__icontains="self-signed").order_by("name").first()
if signing is None:
    signing = CertificateKeyPair.objects.exclude(key_data="").first()

# Scopes: `openid` shapes the JWT (enough when the consumer only checks signature+iss, e.g. ktayl-core's
# .anyRequest().authenticated()). A consumer that checks a `scope` claim (e.g. underwriting requires
# `underwriting:write`) needs that ScopeMapping attached too → pass AK_EXTRA_SCOPES=scope1,scope2 (the
# ScopeMapping.scope_name values; they must already exist). The client must also REQUEST them in its
# client_credentials call (`&scope=...`). First extra-scope caller: ktayl-core→underwriting (SUB-02).
_extra = [s.strip() for s in os.environ.get("AK_EXTRA_SCOPES", "").split(",") if s.strip()]
scopes = list(ScopeMapping.objects.filter(scope_name__in=["openid", *_extra]))

prov, _ = OAuth2Provider.objects.get_or_create(
    name=slug, defaults=dict(authorization_flow=authz, signing_key=signing)
)
prov.authorization_flow = authz
prov.signing_key = signing
prov.client_type = "confidential"
# The M2M grant. Raw GrantTypes string values are stable across versions.
try:
    prov.grant_types = ["client_credentials"]
except Exception:
    pass
# Issuer mode drives the `iss` claim: per_provider → .../application/o/<slug>/ (what an allowlist matches).
try:
    prov.issuer_mode = issuer_mode
except Exception:
    pass
# No redirect URIs for a client-credentials provider.
try:
    prov.redirect_uris = []
except Exception:
    prov.redirect_uris = ""
prov.save()
prov.property_mappings.set(scopes)
prov.save()

app, _ = Application.objects.get_or_create(slug=slug, defaults=dict(name=name))
app.name = name
app.provider = prov
app.save()

# Report the iss the consumer must allowlist (internal-host per-app form).
issuer = f"http://authentik-server.authentik.svc:80/application/o/{slug}/"
print("CLIENTID=%s" % prov.client_id)
print("CLIENTSECRET=%s" % prov.client_secret)
print("ISSUER=%s" % issuer)
print("DONE=1")
