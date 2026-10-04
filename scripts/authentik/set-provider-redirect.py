# pyright: reportMissingImports=false
"""
Update the redirect_uris of an EXISTING Authentik OAuth2 provider (ORM).

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected; see .claude/rules/reusable-scripts.md). Authentik's REST API
403s every token on 2026.5.3, so the ORM via `ak shell` is the only working path.

Why this exists: some OIDC clients send a redirect_uri that differs from what was registered at
creation — e.g. GLPI's glpi-singlesignon plugin appends a `/provider/<id>` PATH_INFO segment
(`…/callback.php/provider/1`), which a STRICT registration of `…/callback.php` rejects. A REGEX
redirect makes the registration tolerate the real value (and future provider ids).

Inputs (environment variables):
  AK_PROVIDER_SLUG   required  the provider/application slug (e.g. "glpi")
  AK_REDIRECT_URIS   required  comma- or newline-separated redirect URIs (regex patterns if REGEX mode)
  AK_MATCH_MODE      optional  "strict" (default) | "regex"

Output (stdout marker): DONE=1

Example (from a host with kubectl):
  bash scripts/authentik/set-provider-redirect.sh glpi \
    'https://itsm\\.devandre\\.sbs/plugins/singlesignon/front/callback\\.php.*' regex
"""
import os

from authentik.providers.oauth2.models import OAuth2Provider

slug = os.environ["AK_PROVIDER_SLUG"]
mode = os.environ.get("AK_MATCH_MODE", "strict").lower()
redirects = [u.strip() for u in os.environ["AK_REDIRECT_URIS"].replace(",", "\n").splitlines() if u.strip()]
if not redirects:
    raise SystemExit("AK_REDIRECT_URIS is empty")

prov = OAuth2Provider.objects.filter(name=slug).first() or OAuth2Provider.objects.get(name__iexact=slug)

# redirect_uris schema differs across versions: new = list[RedirectURI], old = newline string.
try:
    from authentik.providers.oauth2.models import RedirectURI, RedirectURIMatchingMode

    mm = RedirectURIMatchingMode.REGEX if mode == "regex" else RedirectURIMatchingMode.STRICT
    prov.redirect_uris = [RedirectURI(mm, u) for u in redirects]
except ImportError:
    # old string schema has no per-URI matching mode; store the raw values
    prov.redirect_uris = "\n".join(redirects)

prov.save()
print(f"provider={prov.name} pk={prov.pk} mode={mode}")
for u in redirects:
    print("redirect:", u)
print("DONE=1")
