# Source this (NOT execute) on the controller for a ready Vault CLI session against the in-cluster Vault:
#     source scripts/vault/vault-env.sh
#
# Exports VAULT_ADDR + VAULT_SKIP_VERIFY (split-horizon self-signed cert → skip host verify on the
# controller; the data path is on the private LAN) and loads the READ-ONLY ops token from
# ~/.vault-ops-token. No secret is committed — the token is read from disk at source time.
#
# Capability note: the ops token can READ secret/platform/* but NOT write. Writing a platform secret
# (e.g. seeding a DB credential) requires the BREAK-GLASS ROOT token, which is age-encrypted on the
# controller (~/.vault-root-token.age; identity in Vault secret/platform/k3s-backup-age + Vaultwarden):
#     export VAULT_TOKEN=$(age -d -i <identity> ~/.vault-root-token.age)
# Use it only for the specific write, then drop it — don't leave a root session open.
export VAULT_ADDR="${VAULT_ADDR:-https://vault.10.0.0.200.nip.io}"
export VAULT_SKIP_VERIFY="${VAULT_SKIP_VERIFY:-true}"
if [ -r "$HOME/.vault-ops-token" ]; then
  export VAULT_TOKEN="$(cat "$HOME/.vault-ops-token")"
  echo "vault-env: VAULT_ADDR=$VAULT_ADDR (ops token loaded — READ-only on secret/platform/*)" >&2
else
  echo "vault-env: ~/.vault-ops-token not found — set VAULT_TOKEN yourself" >&2
fi
