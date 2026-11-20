# pyright: reportMissingImports=false
"""
Idempotently ensure an Authentik RECOVERY flow exists and is set as the default brand's recovery flow
(ktayl-iam ADR-016). Without a recovery flow, `POST /core/users/{pk}/recovery/` returns
`400 "No recovery flow set"` and no user can set/reset a password — which blocked external-collaborator
onboarding (the invite link) and left the platform with NO password-recovery mechanism at all.

RUNS INSIDE the authentik pod via `ak shell` — the `authentik.*` imports resolve there, NOT locally
(local Pyright import errors are expected; see .claude/rules/reusable-scripts.md). The REST API 403s
every token on this Authentik version, so the ORM via `ak shell` is the working path.

This builds the **token-path** recovery flow: it binds the shipped `default-password-change-prompt`
(new password) + `default-password-change-write` (save) stages. The IAM `createRecoveryLink` token
pre-authenticates the user, so the flow runs straight to the password-set — NO identification/email stage,
hence NO "reset anyone by username" hole. Full user-initiated self-service reset (identification → email a
link) additionally needs Authentik SMTP (EMAIL_HOST is `localhost` today) → a documented follow-up.

Inputs (environment variables):
  AK_FLOW_SLUG   optional  the recovery flow slug           (default: ktayl-recovery-flow)
  AK_FLOW_TITLE  optional  the flow title shown to the user (default: "Reset your password")

Output (stdout markers):
  FLOW=<slug> created=<bool>
  BIND stage=<name> order=<n> created=<bool>
  BRAND=<domain> flow_recovery=<slug>
  DONE=1

Example (from the controller — via ensure-recovery-flow.sh):
  bash scripts/authentik/ensure-recovery-flow.sh
"""
import os

from authentik.brands.models import Brand
from authentik.flows.models import (
    Flow,
    FlowAuthenticationRequirement,
    FlowDesignation,
    FlowStageBinding,
)
from authentik.stages.prompt.models import PromptStage
from authentik.stages.user_write.models import UserWriteStage

slug = os.environ.get("AK_FLOW_SLUG", "ktayl-recovery-flow").strip()
title = os.environ.get("AK_FLOW_TITLE", "Reset your password").strip()

flow, created = Flow.objects.get_or_create(
    slug=slug,
    defaults=dict(
        name="Ktayl Recovery Flow",
        title=title,
        designation=FlowDesignation.RECOVERY,
        # a password reset is run by a logged-OUT user following a recovery token link
        authentication=FlowAuthenticationRequirement.REQUIRE_UNAUTHENTICATED,
    ),
)
print(f"FLOW={slug} created={created}")

# Reuse the stages Authentik ships for its password-change flow: prompt the new password, then write it.
prompt = PromptStage.objects.get(name="default-password-change-prompt")
write = UserWriteStage.objects.get(name="default-password-change-write")
for stage, order in ((prompt, 10), (write, 20)):
    _, b_created = FlowStageBinding.objects.get_or_create(
        target=flow, stage=stage, defaults={"order": order}
    )
    print(f"BIND stage={stage.name} order={order} created={b_created}")

# Point the default brand's recovery flow at it → the "forgot password" + the IAM invite link resolve here.
brand = Brand.objects.get(default=True)
if brand.flow_recovery_id != flow.pk:
    brand.flow_recovery = flow
    brand.save(update_fields=["flow_recovery"])
print(f"BRAND={brand.domain} flow_recovery={brand.flow_recovery.slug}")
print("DONE=1")
