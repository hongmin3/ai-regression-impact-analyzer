#!/usr/bin/env bash
# QA Manual Hub -- backup.
#
# Backs up the two things that cannot be rebuilt from the repository:
#   1. the PostgreSQL database  (pg_dump, custom format)
#   2. the document storage tree (tar.gz)
#
# Both land in $BACKUP_ROOT/<YYYYmmdd-HHMMSS>/ together with a manifest, so a
# database dump is never paired with the wrong file set.
#
#   sudo -u ubuntu /opt/qa-manual-hub/scripts/backup.sh
#
# Cron (daily 02:30):
#   30 2 * * * /opt/qa-manual-hub/scripts/backup.sh >> /opt/qa-manual-hub/logs/backup.log 2>&1

set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/opt/qa-manual-hub}"
DATA_ROOT="${DATA_ROOT:-/srv/qa-manual-hub}"
BACKUP_ROOT="${BACKUP_ROOT:-$DATA_ROOT/backup}"
ENV_FILE="${ENV_FILE:-$APP_ROOT/.env}"

# Retention (spec section 47).  0 disables that tier.
KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"
KEEP_MONTHLY="${KEEP_MONTHLY:-3}"

log() { printf '[backup %s] %s\n' "$(date '+%F %T')" "$*"; }
die() { printf '[backup %s] ERROR: %s\n' "$(date '+%F %T')" "$*" >&2; exit 1; }

[[ -r "$ENV_FILE" ]] || die ".env 를 읽을 수 없습니다: $ENV_FILE"

# Parse the connection string without echoing it anywhere.
DB_URL="$(grep -m1 '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
[[ -n "$DB_URL" ]] || die "DATABASE_URL 을 찾을 수 없습니다."

# postgresql+psycopg://user:pass@host:port/dbname
proto_stripped="${DB_URL#*://}"
credentials="${proto_stripped%@*}"
hostpath="${proto_stripped##*@}"
DB_USER="${credentials%%:*}"
DB_PASS="${credentials#*:}"
hostport="${hostpath%%/*}"
DB_NAME="${hostpath##*/}"
DB_NAME="${DB_NAME%%\?*}"
DB_HOST="${hostport%%:*}"
DB_PORT="${hostport##*:}"
[[ "$DB_PORT" == "$DB_HOST" ]] && DB_PORT=5432

STAMP="$(date '+%Y%m%d-%H%M%S')"
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"

log "대상 디렉터리: $DEST"

# --- 1. database ----------------------------------------------------------- #
log "PostgreSQL 덤프 시작 ($DB_NAME)"
PGPASSWORD="$DB_PASS" pg_dump \
    --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=custom --compress=6 --no-owner --no-privileges \
    --file="$DEST/database.dump" \
    || die "pg_dump 실패"
unset PGPASSWORD
log "덤프 완료: $(du -h "$DEST/database.dump" | cut -f1)"

# --- 2. storage ------------------------------------------------------------ #
if [[ -d "$DATA_ROOT/storage" ]]; then
    log "문서 저장소 아카이브 시작"
    tar -czf "$DEST/storage.tar.gz" -C "$DATA_ROOT" storage \
        || die "storage 아카이브 실패"
    log "아카이브 완료: $(du -h "$DEST/storage.tar.gz" | cut -f1)"
else
    log "경고: $DATA_ROOT/storage 가 없습니다. 저장소 백업을 건너뜁니다."
fi

# --- 3. manifest ----------------------------------------------------------- #
{
    echo "backup_at=$(date -Iseconds)"
    echo "hostname=$(hostname)"
    echo "database=$DB_NAME"
    echo "storage_root=$DATA_ROOT/storage"
    echo "storage_file_count=$(find "$DATA_ROOT/storage" -type f 2>/dev/null | wc -l)"
    echo "app_commit=$(cat "$APP_ROOT/app/REVISION" 2>/dev/null || echo unknown)"
    echo "--- sha256 ---"
    (cd "$DEST" && sha256sum ./* 2>/dev/null | grep -v manifest.txt || true)
} > "$DEST/manifest.txt"

chmod -R go-rwx "$DEST"
log "manifest 작성 완료"

# --- 4. retention ---------------------------------------------------------- #
prune() {
    local keep=$1 pattern=$2 label=$3
    (( keep > 0 )) || return 0
    mapfile -t victims < <(
        find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -name "$pattern" \
            | sort -r | tail -n "+$((keep + 1))"
    )
    for dir in "${victims[@]:-}"; do
        [[ -n "$dir" ]] || continue
        log "$label 보존 정책에 따라 삭제: $(basename "$dir")"
        rm -rf -- "$dir"
    done
}

# Daily tier only; weekly/monthly promotion is a documented manual step so the
# script never deletes something a human meant to keep.
prune "$KEEP_DAILY" '20*-*' 'daily'

log "완료. 총 백업 용량: $(du -sh "$BACKUP_ROOT" 2>/dev/null | cut -f1)"
