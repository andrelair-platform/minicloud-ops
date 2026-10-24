#!/bin/bash
# Off-site DR mirror: controller MinIO backup bucket -> Cloudflare R2.
#
# WHY: Longhorn (and the kine/vault snapshots) back up to the controller's LOCAL MinIO
# (10.0.0.1:9000) — same room, same failure domain as the cluster. A room-level loss
# (power/fire/theft) would take the backups with it. This mirrors the backup bucket to R2
# (off-site, different provider — the same R2 account CNPG/barman already uses), giving a
# 3-2-1 off-site copy. Addresses minicloud-gitops#1936 (DORA Art. 11-12 business continuity).
#
# WHERE IT RUNS: controller, as user `ktayl` (owns the `mc` aliases), via the systemd timer
# `minicloud-longhorn-r2-mirror.timer` (daily, after the 02:00 Longhorn backup). Off-cluster
# on purpose — DR tooling must work when the cluster is down, and MinIO is controller-local.
#
# DESIGN: `mc mirror --overwrite --remove` so R2 tracks MinIO EXACTLY. Longhorn manages its
# own block-chain retention in MinIO (incremental backups reference older blocks), so R2 must
# replicate MinIO's *managed* state — naive age-pruning of R2 would corrupt backup chains.
# GUARD: `--remove` means a wiped/broken source would propagate the deletion to the ONLY
# off-site copy. So we ABORT if the source bucket has fewer than MIN_SRC_OBJECTS — the off-site
# copy is never destroyed because the primary looks empty.
#
# USAGE:  mirror-minio-to-r2.sh [SRC_BUCKET] [DST_BUCKET]
#   defaults: SRC=minilocal/longhorn  DST=r2cnpg/minicloud-longhorn-offsite
# Parameterized so the same script can mirror other backup buckets (db-backups, k3s-backup)
# by passing args / adding more timer instances.

set -euo pipefail

MC="${MC:-/home/ktayl/.local/bin/mc}"
SRC_ALIAS_BUCKET="${1:-minilocal/longhorn}"
DST_ALIAS_BUCKET="${2:-r2cnpg/minicloud-longhorn-offsite}"
MIN_SRC_OBJECTS="${MIN_SRC_OBJECTS:-50}"   # safety floor: refuse to mirror-with-remove below this

# Log to STDOUT only. The systemd unit captures stdout via StandardOutput=append:<logfile>
# (written as root); a manual run prints to the terminal. The script must NOT also write the
# file itself — a second writer (as ktayl) would hit permission-denied on the root-owned append
# target (abort under set -e) and duplicate every line. stdout is the single source.
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" ; }

log "=== off-site mirror start: ${SRC_ALIAS_BUCKET} -> ${DST_ALIAS_BUCKET} ==="

# Preflight 1: mc + both aliases reachable
command -v "$MC" >/dev/null 2>&1 || { log "FATAL: mc not found at $MC"; exit 1; }
SRC_ALIAS="${SRC_ALIAS_BUCKET%%/*}"
DST_ALIAS="${DST_ALIAS_BUCKET%%/*}"
"$MC" ls "$SRC_ALIAS" >/dev/null 2>&1 || { log "FATAL: source alias '$SRC_ALIAS' unreachable"; exit 1; }
"$MC" ls "$DST_ALIAS" >/dev/null 2>&1 || { log "FATAL: dest alias '$DST_ALIAS' unreachable";   exit 1; }

# Preflight 2: SAFETY — refuse to --remove against a suspiciously empty source (don't let a
# wiped/broken primary destroy the off-site copy). Count objects cheaply via `mc du`.
SRC_OBJECTS="$("$MC" du "$SRC_ALIAS_BUCKET" 2>/dev/null | grep -oE '[0-9]+ objects' | grep -oE '^[0-9]+' || echo 0)"
log "source object count: ${SRC_OBJECTS} (floor: ${MIN_SRC_OBJECTS})"
if [ "${SRC_OBJECTS:-0}" -lt "$MIN_SRC_OBJECTS" ]; then
  log "ABORT: source has ${SRC_OBJECTS} objects (< ${MIN_SRC_OBJECTS}) — refusing to mirror-with-remove over the off-site copy. Investigate the primary backup bucket."
  exit 2
fi

# Mirror: --overwrite (update changed) + --remove (delete from R2 what left MinIO = track retention)
log "mirroring (--overwrite --remove)…"
"$MC" mirror --overwrite --remove "$SRC_ALIAS_BUCKET" "$DST_ALIAS_BUCKET" 2>&1

# Report resulting off-site footprint
DST_DU="$("$MC" du "$DST_ALIAS_BUCKET" 2>/dev/null | tail -1 || echo '?')"
log "=== mirror complete. off-site now: ${DST_DU} ==="
