#!/usr/bin/env bash
# HR-12 — live proof of the J/M/L signed-event backbone, independent of the ERPNext image.
#
# Reproduces exactly what erpnext_hr_lifecycle.events.publish() does: builds a canonical lifecycle
# event, HMAC-SHA256 signs it with the real HR_LIFECYCLE_SIGNING_KEY (read from the in-cluster secret),
# publishes it to NATS JetStream HR_LIFECYCLE with an HR-Signature header, then reads the message back
# off the stream and RE-VERIFIES the signature — proving the stream accepts the event and a consumer
# (ktayl-iam v3 / the n8n fan-out) can trust it.
#
# Run on the controller (needs kubectl → erp secret + messaging nats-box). Idempotent (purge-safe:
# it reads the last message, doesn't assume an empty stream).
#
# Usage:  scripts/hr-lifecycle/verify-stream.sh [joiner|mover|leaver]
set -euo pipefail
EVENT="${1:-joiner}"
STREAM=HR_LIFECYCLE
SUBJECT="hr.lifecycle.${EVENT}"
NATS_BOX=$(kubectl get pod -n messaging -l app.kubernetes.io/component=nats-box -o jsonpath='{.items[0].metadata.name}')

# 1. the real signing key the producer + consumers share
KEY=$(kubectl get secret erpnext-hr-lifecycle -n erp -o jsonpath='{.data.HR_LIFECYCLE_SIGNING_KEY}' | base64 -d)
[ -n "$KEY" ] || { echo "ERROR: empty HR_LIFECYCLE_SIGNING_KEY" >&2; exit 1; }

# 2. canonical event body + signature (same canonical_bytes/sign as events.py: sorted keys, no spaces
#    BETWEEN elements — string values keep their spaces, so emit SIG and BODY on separate lines, no split)
OUT=$(KEY="$KEY" EVENT="$EVENT" python3 - <<'PY'
import hashlib, hmac, json, os
ev = {
    "schema": "ktayl.hr.lifecycle/v1",
    "event": os.environ["EVENT"],
    "occurred_at": "2026-10-04T00:00:00+00:00",
    "effective_date": "2026-10-04",
    "source": "erpnext",
    "subject": {"matricule": "100002", "employee_name": "Marie Leclerc",
                "job": "Souscripteur", "department": "Souscription - KS",
                "entity": "Ktayl Solutions", "country": "France", "status": "Active"},
}
body = json.dumps(ev, sort_keys=True, separators=(",", ":")).encode()
sig = hmac.new(os.environ["KEY"].encode(), body, hashlib.sha256).hexdigest()
print(sig)            # line 1
print(body.decode())  # line 2 (compact JSON, single line)
PY
)
SIG=$(printf '%s\n' "$OUT" | sed -n '1p')
BODY=$(printf '%s\n' "$OUT" | sed -n '2p')
echo "event    = $EVENT"
echo "subject  = $SUBJECT"
echo "signature= ${SIG:0:16}…"

# 3. publish to the stream with the signature header
kubectl exec -n messaging "$NATS_BOX" -- nats --no-context -s nats://nats.messaging.svc:4222 \
  pub "$SUBJECT" "$BODY" -H "HR-Signature:$SIG" >/dev/null
echo "published → $STREAM"

# 4. read the newest message back + re-verify the signature (what a consumer does)
LAST=$(kubectl exec -n messaging "$NATS_BOX" -- nats --no-context -s nats://nats.messaging.svc:4222 \
  stream get "$STREAM" --last-for "$SUBJECT" -j)
KEY="$KEY" python3 - "$LAST" <<'PY'
import base64, hashlib, hmac, json, os, sys
msg = json.loads(sys.argv[1])
body = base64.b64decode(msg["data"])
# NATS JetStream returns the raw header block base64 in "hdrs": "NATS/1.0\r\nHR-Signature: <sig>\r\n\r\n"
got = ""
raw = base64.b64decode(msg.get("hdrs", "")).decode("utf-8", "replace") if msg.get("hdrs") else ""
for line in raw.split("\r\n"):
    if line.lower().startswith("hr-signature:"):
        got = line.split(":", 1)[1].strip()
want = hmac.new(os.environ["KEY"].encode(), body, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(got, want)
print("read back:", body.decode()[:80], "…")
print("signature header:", (got[:16] + "…") if got else "(none)")
print("signature verified:", ok)
sys.exit(0 if ok else 1)
PY
echo "HR-12 backbone PROVEN: signed $EVENT event landed on $STREAM and its signature verifies."
