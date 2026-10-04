# HR-12 — n8n non-access fan-out (import runbook)

The ERPNext side already emits signed J/M/L events. This n8n workflow is the **non-access fan-out**:
it receives each event, verifies the HMAC, opens a **GLPI software-provisioning ticket**, and sends an
**email**. No hardware (BYOD); access (Authentik groups) is ktayl-iam's job, never here.

```
erpnext_hr_lifecycle.publish()  --POST signed event-->  n8n webhook /hr-lifecycle
   -> Code: verify X-HR-Signature (HMAC-SHA256, $env.HR_LIFECYCLE_SIGNING_KEY)
   -> GLPI initSession -> create Ticket (type=request)   [$env.GLPI_* ]
   -> Email (Stalwart SMTP, already configured on n8n)
   -> respond 200
```

## Already wired for you (platform side — committed)
- **n8n env** (gitops `manifests/n8n/03-deployment.yaml`): `envFrom n8n-hr-glpi` (GLPI_APP_TOKEN,
  GLPI_USER_TOKEN, GLPI_API_URL, HR_LIFECYCLE_SIGNING_KEY) + `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` +
  `NODE_FUNCTION_ALLOW_BUILTIN=crypto` (so the Code node can read `$env` and `require('crypto')`).
- **GLPI REST API** enabled + an unrestricted apiclient + a user api_token
  (`minicloud-ops/scripts/glpi/enable-api.sh`), tokens in secret `automation/n8n-hr-glpi`.
- **Netpol** `allow-automation-smtp` (manifests/network-policies/mail.yaml) opens `automation` → `stalwart:587`
  (the `mail` ns is default-deny-ingress). Without it the SMTP credential test times out.

## Your step — import + activate (UI, ~3 min)
1. Open **https://n8n.devandre.sbs** → **Workflows → Import from File** → pick
   `scripts/hr-lifecycle/n8n-fanout-workflow.json`.
2. On the **Notify (email)** node, create the **SMTP credential** (n8n's `emailSend` uses a stored credential,
   NOT the `N8N_SMTP_*` env which only drives n8n's own system mail):
   - Host `stalwart.mail.svc.cluster.local` · Port `587` · **SSL/TLS off** · (leave *Disable STARTTLS* off)
   - User `admin@devandre.sbs` · Password = Vault `secret/platform/mail` key **`stalwart-admin-secret`**
     (NOT `smtp-relay-password`, which is the SES outbound cred → `535 invalid`).
   - The node's `options.allowUnauthorizedCerts: true` is already set in the JSON (Stalwart presents a
     self-signed cert on 587; STARTTLS still encrypts — the accepted internal-hop posture).
   > TODO (least-privilege): replace the admin account with a dedicated `noreply@devandre.sbs` sender.
3. **Save**, then toggle **Active** (top-right). The production webhook becomes
   `http://n8n.automation.svc:5678/webhook/hr-lifecycle` (in-cluster) /
   `https://n8n.devandre.sbs/webhook/hr-lifecycle` (public).
4. (Optional) adjust the **email recipient** — it defaults to `it@devandre.sbs`; change the
   `Notify (email)` node's `toEmail` if you want a different inbox.

> The workflow references `$env.GLPI_API_URL/APP_TOKEN/USER_TOKEN` and
> `$env.HR_LIFECYCLE_SIGNING_KEY` — those are injected from the `n8n-hr-glpi` secret (step above), so
> no n8n credentials to create. If a node shows an env-access warning, confirm the n8n pod rolled with
> the new env (`kubectl rollout restart deploy/n8n -n automation`).

## Then tell me (or run yourself) — flip ERPNext's fan-out on
Once the workflow is **Active**, point ERPNext's `publish()` at it by setting the webhook URL in the
bootstrapped secret (publish() skips the fan-out while this is empty):
```bash
# on the controller
kubectl patch secret erpnext-hr-lifecycle -n erp --type merge \
  -p "{\"stringData\":{\"HR_N8N_WEBHOOK_URL\":\"http://n8n.automation.svc:5678/webhook/hr-lifecycle\"}}"
kubectl rollout restart deploy/erpnext-gunicorn deploy/erpnext-worker-s -n erp   # pick up the env
```

## Verify end-to-end
```bash
# fire a test lifecycle event from ERPNext (admin); it publishes to NATS AND POSTs the n8n fan-out
kubectl exec -n erp deploy/erpnext-gunicorn -- \
  bench --site erp.devandre.sbs execute erpnext_hr_lifecycle.events.emit_test_event \
  --kwargs "{'event_type':'joiner'}"
```
Then check: n8n **Executions** shows a success, a new **GLPI ticket** exists, and the email arrived.

## Notes / gotchas
- **HMAC is over the raw canonical body** ERPNext signed (sorted keys, no spaces) — the webhook uses
  `rawBody: true` and the Code node verifies the exact bytes; do not add a JSON-reparse before it.
- **A fan-out failure never affects HR** — `publish()` POSTs best-effort in a background job; if n8n is
  down/inactive the event still lands on the durable NATS `HR_LIFECYCLE` stream.
- **Node typeVersions** target current n8n; if your version differs, open each node and re-save (n8n
  auto-migrates) — logic is unchanged.
- GLPI ticket `type: 2` = Request. The apiclient/user-token come from `scripts/glpi/enable-api.sh`
  (re-run it after a GLPI DB rebuild).
