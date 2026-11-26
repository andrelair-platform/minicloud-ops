#!/usr/bin/env bash
# cyber-copy.sh — push the crown jewels (kine + the Vault raft snapshot) from MinIO to the AWS S3
# Object-Lock Cyber-Recovery vault (ADR-0003, minicloud-cloud). The 3rd DR layer: MinIO (operational)
# / Cloudflare R2 (disaster recovery) / AWS S3 Object Lock (cyber recovery — immutable, independent
# provider, survives ransomware or a credential compromise that deletes the other backups).
#
# DEPLOYED to ~/bin/cyber-copy.sh on the controller; run by the `cyber-copy` cron (05:35 daily — after
# the 02:30 kine/vault backups and the 05:00 longhorn R2 mirror).  Install: copy to ~/bin + the cron line
#   35 5 * * * /home/ktayl/bin/cyber-copy.sh >> /home/ktayl/.local/log/cyber-copy.log 2>&1
#
# CREDS — SHORT-LIVED STS minted at runtime via the Vault AWS secrets engine; NO static key on disk:
#   Vault role `aws/sts/cyber-recovery-write` (assumed_role → ktayl-cyber-recovery-writer, ADD-ONLY).
#   The controller holds only a scoped periodic token ~/.vault-cyber-copy-token (policy `cyber-copy` =
#   read aws/sts/cyber-recovery-write) — same pattern as ~/.vault-snapshot-token.
#
# IMMUTABILITY — the bucket's default Object Lock (GOVERNANCE 35d) locks every PutObject; the Writer role
#   is add-only (no Delete, no BypassGovernanceRetention), and this script skips keys already present (so
#   it never re-PUTs a locked object). Keys are the backups' own timestamps → one locked object per day.
#
# DEPS: mc (minilocal alias), aws cli, ~/.local/bin/vault, python3.  Bucket + IAM role: minicloud-cloud
#   (s3-cyber-recovery.tf + s3-cyber-recovery-vault-auth.tf).  Reader restore path: ktayl-cyber-recovery-read.
set -euo pipefail

BUCKET="minicloud-cyber-recovery-625830750465"
VA="https://vault.10.0.0.200.nip.io"
MC="$HOME/.local/bin/mc"
VAULT="$HOME/.local/bin/vault"

# mint short-lived STS (assumes the add-only writer role) using the scoped controller token
C=$(VAULT_ADDR="$VA" VAULT_SKIP_VERIFY=true VAULT_TOKEN="$(cat "$HOME/.vault-cyber-copy-token")" \
      "$VAULT" write -f -format=json aws/sts/cyber-recovery-write)
g() { printf '%s' "$C" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['$1'])"; }
export AWS_ACCESS_KEY_ID="$(g access_key)"
export AWS_SECRET_ACCESS_KEY="$(g secret_key)"
export AWS_SESSION_TOKEN="$(g security_token)"
export AWS_DEFAULT_REGION="eu-west-1"

mkdir -p /tmp/cyber
for sub in kine vault; do
  LATEST=$("$MC" ls "minilocal/db-backups/$sub/" 2>/dev/null | awk '{print $NF}' | sort | tail -1)
  [ -z "${LATEST:-}" ] && { echo "  no $sub backup found"; continue; }
  if aws s3api head-object --bucket "$BUCKET" --key "$sub/$LATEST" >/dev/null 2>&1; then
    echo "  $sub/$LATEST already in vault (skip, add-only)"
  else
    "$MC" cp -q "minilocal/db-backups/$sub/$LATEST" "/tmp/cyber/$LATEST"
    aws s3 cp --only-show-errors "/tmp/cyber/$LATEST" "s3://$BUCKET/$sub/$LATEST"
    rm -f "/tmp/cyber/$LATEST"
    echo "  $sub/$LATEST -> cyber-recovery vault (Object Lock applied)"
  fi
done
echo "cyber-copy done"
