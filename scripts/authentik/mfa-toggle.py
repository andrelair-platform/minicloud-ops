# pyright: reportMissingImports=false
"""
Toggle global MFA enforcement in Authentik by enabling/disabling the Authenticator Validation
stage binding(s) in every `authentication`-designation flow (the shared login flow). Reversible:
disabling only flips FlowStageBinding.enabled, it does NOT delete the stage or anyone's TOTP device.

RUNS INSIDE the authentik pod via `ak shell` (the authentik.* imports resolve there, not locally).

Input (environment):
  MFA_ENABLED   "true" to enforce MFA, "false" to skip it (default "true")

Output markers (captured by the runner):
  MFA_CHANGED=<n> MFA_ENABLED=<bool>
"""
import os

from authentik.flows.models import Flow, FlowStageBinding
from authentik.stages.authenticator_validate.models import AuthenticatorValidateStage

enabled = os.environ.get("MFA_ENABLED", "true").lower() in ("1", "true", "yes", "on")

validate_stage_ids = set(AuthenticatorValidateStage.objects.values_list("stage_ptr_id", flat=True))
flows = Flow.objects.filter(designation="authentication")

changed = []
for flow in flows:
    for binding in FlowStageBinding.objects.filter(target=flow):
        if binding.stage_id in validate_stage_ids and binding.enabled != enabled:
            binding.enabled = enabled
            binding.save()
            changed.append(f"{flow.slug}:{binding.stage}")

print(f"MFA_CHANGED={len(changed)} MFA_ENABLED={enabled}")
for c in changed:
    print(" -", c)
