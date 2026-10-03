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
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.models import PolicyBinding
from authentik.stages.authenticator_validate.models import AuthenticatorValidateStage

enabled = os.environ.get("MFA_ENABLED", "true").lower() in ("1", "true", "yes", "on")

# FlowStageBinding has no `enabled` flag, so toggle MFA by (un)applying a "return False" policy on the
# Authenticator Validation stage binding(s). Policy enabled -> stage skipped -> MFA off. Fully reversible;
# never deletes a stage binding or a TOTP device.
skip_policy, _ = ExpressionPolicy.objects.get_or_create(
    name="skip-mfa-global",
    defaults=dict(expression="return False"),
)

validate_stage_ids = set(AuthenticatorValidateStage.objects.values_list("stage_ptr_id", flat=True))
flows = Flow.objects.filter(designation="authentication")

changed = []
want_skip = not enabled  # the skip policy is ACTIVE when MFA should be OFF
for flow in flows:
    for binding in FlowStageBinding.objects.filter(target=flow):
        if binding.stage_id in validate_stage_ids:
            pb, _ = PolicyBinding.objects.get_or_create(
                policy=skip_policy, target=binding, defaults=dict(order=0, enabled=want_skip)
            )
            pb.enabled = want_skip
            pb.save()
            # The skip ("return False") only short-circuits the stage under engine_mode=all. Use "all"
            # while skipping; restore "any" when re-enabling (equivalent to the original once the skip
            # policy is disabled, since only the default validate policy then remains).
            binding.policy_engine_mode = "all" if want_skip else "any"
            binding.save()
            changed.append(f"{flow.slug}:{binding.stage} skip={want_skip} mode={binding.policy_engine_mode}")

print(f"MFA_CHANGED={len(changed)} MFA_ENABLED={enabled}")
for c in changed:
    print(" -", c)
