#!/usr/bin/env bash
# QA Manual Hub -- restore from a backup directory.
#
#   sudo ./restore.sh /srv/qa-manual-hub/backup/20260827-023000
#
# This script OVERWRITES the live database and document storage.  It therefore:
#   * prints exactly what it will replace,
#   * requires you to type RESTORE to continue (or pass --yes),
#   * takes a safety backup of the current state first,
#   * stops the service before, and starts it after.
#
# Nothing runs until you confirm.

set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/opt/qa-manual-hub}"
DATA_ROOT="${DATA_ROOT:-/srv/qa-manual-hub}"
ENV_FILE="${ENV_FILE:-$APP_ROOT/.env}"
SERVICE="${SERVICE:-qa-manual-hub}"

log()  { printf '\033[1;34m[restore]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

SOURCE="${1:-}"
ASSUME_YES=0
[[ "${2:-}" == "--yes" || "${1:-}" == "--yes" ]] && ASSUME_YES=1
[[ "$SOURCE" == "--yes" ]] && SOURCE="${2:-}"

[[ $EUID -eq 0 ]] || die "root 권한이 필요합니다: sudo $0 <backup_dir>"
[[ -n "$SOURCE" ]] || die "사용법: $0 <backup_dir> [--yes]"
[[ -d "$SOURCE" ]] || die "백업 디렉터리가 없습니다: $SOURCE"
[[ -f "$SOURCE/database.dump" ]] || die "database.dump 가 없습니다: $SOURCE"
[[ -r "$ENV_FILE" ]] || die ".env 를 읽을 수 없습니다: $ENV_FILE"

DB_URL="$(grep -m1 '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
proto_stripped="${DB_URL#*://}"
credentials="${proto_stripped%@*}"
hostpath="${proto_stripped##*@}"
DB_USER="${credentials%%:*}"
DB_PASS="${credentials#*:}"
hostport="${hostpath%%/*}"
DB_NAME="${hostpath##*/}"
DB_HOST="${hostport%%:*}"
DB_PORT="${hostport##*:}"
[[ "$DB_PORT" == "$DB_HOST" ]] && DB_PORT=5432

echo
cat <<EOF
==========================================================
  복원 대상 확인
----------------------------------------------------------
  백업 소스   : $SOURCE
  $( [[ -f "$SOURCE/manifest.txt" ]] && grep -E '^(backup_at|storage_file_count)' "$SOURCE/manifest.txt" | sed 's/^/  /' )

  덮어쓸 데이터베이스 : $DB_NAME @ $DB_HOST:$DB_PORT
  덮어쓸 저장소       : $DATA_ROOT/storage
                        (현재 파일 $(find "$DATA_ROOT/storage" -type f 2>/dev/null | wc -l)개)

  이 작업은 현재 데이터를 대체합니다.
  진행 전 현재 상태를 $DATA_ROOT/backup/pre-restore-* 에 백업합니다.
==========================================================
EOF

if (( ! ASSUME_YES )); then
    read -rp "계속하려면 RESTORE 를 입력하세요: " answer
    [[ "$answer" == "RESTORE" ]] || die "취소되었습니다."
fi

# --- 0. safety backup of the CURRENT state --------------------------------- #
SAFETY="$DATA_ROOT/backup/pre-restore-$(date '+%Y%m%d-%H%M%S')"
log "현재 상태 안전 백업: $SAFETY"
mkdir -p "$SAFETY"
PGPASSWORD="$DB_PASS" pg_dump --host="$DB_HOST" --port="$DB_PORT" \
    --username="$DB_USER" --dbname="$DB_NAME" --format=custom --compress=6 \
    --no-owner --no-privileges --file="$SAFETY/database.dump" \
    || warn "현재 DB 백업 실패 (계속 진행합니다)"
if [[ -d "$DATA_ROOT/storage" ]]; then
    tar -czf "$SAFETY/storage.tar.gz" -C "$DATA_ROOT" storage \
        || warn "현재 storage 백업 실패 (계속 진행합니다)"
fi
unset PGPASSWORD
# This script runs as root, so the safety backup would otherwise be root-owned
# and the service account could not prune it afterwards.
chown -R "$(stat -c '%U:%G' "$DATA_ROOT")" "$SAFETY"

# --- 1. stop the service --------------------------------------------------- #
log "서비스 정지: $SERVICE"
systemctl stop "$SERVICE" || warn "$SERVICE 가 실행 중이 아니었습니다."

# --- 2. database ----------------------------------------------------------- #
log "데이터베이스 복원 (public 스키마 재생성)"
PGPASSWORD="$DB_PASS" psql --host="$DB_HOST" --port="$DB_PORT" \
    --username="$DB_USER" --dbname="$DB_NAME" -q \
    -c 'DROP SCHEMA IF EXISTS public CASCADE' \
    -c 'CREATE SCHEMA public' \
    || die "스키마 재생성 실패"

PGPASSWORD="$DB_PASS" pg_restore --host="$DB_HOST" --port="$DB_PORT" \
    --username="$DB_USER" --dbname="$DB_NAME" \
    --no-owner --no-privileges --exit-on-error \
    "$SOURCE/database.dump" \
    || die "pg_restore 실패. 안전 백업으로 되돌리세요: $SAFETY"
unset PGPASSWORD
log "데이터베이스 복원 완료"

# --- 3. storage ------------------------------------------------------------ #
if [[ -f "$SOURCE/storage.tar.gz" ]]; then
    log "문서 저장소 복원"
    STAGE="$(mktemp -d "$DATA_ROOT/.restore-XXXXXX")"
    tar -xzf "$SOURCE/storage.tar.gz" -C "$STAGE" || die "storage 압축 해제 실패"
    if [[ -d "$DATA_ROOT/storage" ]]; then
        mv "$DATA_ROOT/storage" "$DATA_ROOT/storage.replaced-$(date '+%Y%m%d-%H%M%S')"
    fi
    mv "$STAGE/storage" "$DATA_ROOT/storage"
    rmdir "$STAGE"
    chown -R "$(stat -c '%U:%G' "$DATA_ROOT")" "$DATA_ROOT/storage"
    chmod 750 "$DATA_ROOT/storage"
    log "저장소 복원 완료 (기존 폴더는 storage.replaced-* 로 보존)"
else
    warn "storage.tar.gz 가 없습니다. 파일은 복원하지 않았습니다."
fi

# --- 4. schema version + restart ------------------------------------------- #
# The dump may predate the current code, so bring the schema forward.  Both this
# and the integrity check below need the deployment environment, which is why
# they go through `sudo -u ... env DATABASE_URL=... STORAGE_ROOT=...` rather than
# relying on the caller's shell.
SERVICE_USER="$(stat -c '%U' "$APP_ROOT")"
BACKEND_DIR="$APP_ROOT/app/backend"
STORAGE_ROOT_VALUE="$(grep -m1 '^STORAGE_ROOT=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')"
: "${STORAGE_ROOT_VALUE:=$DATA_ROOT/storage}"

run_as_service() {
    sudo -u "$SERVICE_USER" env \
        DATABASE_URL="$DB_URL" \
        STORAGE_ROOT="$STORAGE_ROOT_VALUE" \
        "$@"
}

log "마이그레이션 상태 확인"
if [[ -f "$BACKEND_DIR/alembic.ini" ]]; then
    (cd "$BACKEND_DIR" && run_as_service "$APP_ROOT/venv/bin/alembic" upgrade head) \
        || warn "alembic upgrade 실패. 수동으로 확인하세요."
fi

log "서비스 시작"
systemctl start "$SERVICE"
sleep 3
systemctl is-active --quiet "$SERVICE" \
    && log "서비스 정상 동작" \
    || die "서비스가 시작되지 않았습니다: journalctl -u $SERVICE -n 50"

log "파일 무결성 점검"
(cd "$BACKEND_DIR" && run_as_service "$APP_ROOT/venv/bin/python" -m app.cli check-storage) \
    || warn "일부 파일이 누락되었습니다. 위 목록을 확인하세요."

echo
log "복원 완료. 안전 백업 위치: $SAFETY"
log "문제가 없으면 storage.replaced-* 와 안전 백업을 정리하세요."
