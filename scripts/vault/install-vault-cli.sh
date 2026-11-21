#!/usr/bin/env bash
# Install the HashiCorp Vault CLI into ~/.local/bin on the controller (no sudo — same home as the existing
# vault-snapshot/ops tooling, already on PATH). Idempotent: re-run to upgrade. The platform's Vault tooling
# historically shelled out to `curl` because the CLI wasn't present; this fills that gap.
#
# Usage:   scripts/vault/install-vault-cli.sh [version]
#   [version] — a Vault version (e.g. 2.2.2); omitted = the latest stable from the HashiCorp releases API.
# Run ON the controller (it has internet via NAT). After install, source scripts/vault/vault-env.sh for a
# ready session (ops token = read-only; writes to secret/platform/* need the break-glass root token).
set -euo pipefail
ARCH=$(dpkg --print-architecture 2>/dev/null || uname -m)
case "$ARCH" in amd64|x86_64) A=amd64;; arm64|aarch64) A=arm64;; *) A="$ARCH";; esac
VER="${1:-}"
if [ -z "$VER" ]; then
  VER=$(curl -fsSL https://api.releases.hashicorp.com/v1/releases/vault/latest \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])')
fi
echo "installing vault ${VER} (linux_${A}) → ~/.local/bin" >&2
mkdir -p ~/.local/bin ~/.cache/vault-dl
cd ~/.cache/vault-dl
curl -fsSL -o vault.zip "https://releases.hashicorp.com/vault/${VER}/vault_${VER}_linux_${A}.zip"
unzip -oq vault.zip vault
install -m 0755 vault ~/.local/bin/vault
rm -f vault.zip vault
echo "installed: $(~/.local/bin/vault version)" >&2
