# Deployment

## systemd vs Docker Compose 선택 기준
<!-- akela: id=systemd-vs-docker -->

이 저장소는 두 배포 경로를 모두 제공한다.

- **네이티브 systemd** (`deploy/systemd`, `deploy/scripts`) — 서버에 이미 PostgreSQL 이 있거나,
  같은 호스트에서 보호해야 할 다른 서비스가 돌고 있을 때 선택한다. Docker 가 iptables 를 조작해
  기존 방화벽 정책을 우회하는 문제를 피할 수 있고, PostgreSQL 인스턴스가 이중화되지 않는다.
- **Docker Compose** (`deploy/docker-compose.yml`) — 깨끗한 호스트나 로컬 개발 환경에서
  가장 빠른 경로.

자세한 판단 근거는 `deploy/docker-compose.yml` 상단 주석에 있다.

## 사전 조건 (systemd 배포)
<!-- akela: id=prerequisites -->

- Ubuntu 22.04 / 24.04 (다른 systemd 리눅스도 동작)
- PostgreSQL 14 이상이 이미 구동 중 (`psql` 로 접속 가능)
- Python 3.11 이상
- 개발 PC에 Node.js 20 이상 (프론트엔드 빌드용, 서버에는 불필요)

## 설치 (install.sh) — 멱등, 추가 작업만 수행
<!-- akela: id=install-script -->

```bash
sudo ./deploy/scripts/install.sh
```

- nginx / python3-venv / rsync 중 없는 것만 apt 설치
- `<APP_ROOT>`, `<DATA_ROOT>` 디렉터리 생성
- 전용 DB(`qa_manual_hub`)와 전용 role(`qamanual`) 생성. **이미 있으면 그대로 사용하고 절대 초기화하지 않음**
- 무작위 DB 비밀번호로 `.env` 생성 (600, 이미 있으면 유지)
- virtualenv 생성 + 의존성 설치
- systemd 유닛 설치 및 enable
- nginx 사이트 설치
- UFW 가 active 면 `80/tcp` 규칙 1개만 추가
- 사전 점검에서 백엔드 포트 충돌이나 PostgreSQL 접속 실패를 발견하면 **아무것도 바꾸지 않고 중단**

환경변수로 조정 가능: `APP_ROOT`, `DATA_ROOT`, `BACKEND_PORT`, `DB_NAME`, `DB_USER`, `SERVICE_USER`, `SKIP_NGINX`, `SKIP_UFW`.

## 코드 배포 (deploy.sh)
<!-- akela: id=deploy-script -->

개발 PC에서 실행:

```bash
./deploy/scripts/deploy.sh user@server
```

순서: 프론트엔드 빌드 → 백엔드·SPA 전송 → 의존성 동기화 → `alembic upgrade head` → 서비스 재시작 → 헬스체크(최대 30초 재시도).

`rsync` 가 없는 환경(예: Windows Git Bash)에서는 tar 파이프로 대체한다.

**롤백**: 이전 커밋을 체크아웃해 다시 `deploy.sh` 실행. 스키마 변경이 포함된 경우 `alembic downgrade` 를 먼저 검토.

## 최초 관리자 생성 및 시드
<!-- akela: id=bootstrap-admin-seed -->

```bash
sudo -u <SERVICE_USER> <APP_ROOT>/scripts/qamh bootstrap-admin
<APP_ROOT>/scripts/qamh seed-catalog --product "제품명"
```

- 비밀번호는 대화형 입력, 최초 로그인 시 변경 요구가 기본. 초기 비밀번호는 소스코드·저장소·설정 파일 어디에도 저장되지 않음
- 비대화형 필요 시 `BOOTSTRAP_ADMIN_PASSWORD` 환경변수로 1회 전달
- `seed-catalog` 는 문서 분류 10종 + 지정 제품을 생성 (이미 있으면 건너뜀)

## 관리 CLI
<!-- akela: id=admin-cli -->

```bash
<APP_ROOT>/scripts/qamh <command>
```

| 명령 | 설명 |
|---|---|
| `bootstrap-admin` | 최초 관리자 생성 (이미 있으면 `--force` 필요) |
| `seed-catalog [--product NAME]` | 기본 문서 분류(및 제품) 생성 |
| `reset-password <login_id>` | 비밀번호 강제 변경 — 관리자 잠김 복구용. 해당 세션 전부 무효화 |
| `list-users` | 사용자 목록 |
| `check-storage` | DB에 등록된 모든 버전의 파일 존재·크기 검증. 문제 있으면 종료코드 2 |
| `purge-sessions` | 만료 세션 정리 |

래퍼가 `.env` 를 자동 로드하므로 어느 경로에서 실행해도 된다.

## 백업 절차
<!-- akela: id=backup-procedure -->

```bash
<APP_ROOT>/scripts/backup.sh
```

`<DATA_ROOT>/backup/<YYYYmmdd-HHMMSS>/` 에 3개 파일 생성:

| 파일 | 내용 |
|---|---|
| `database.dump` | `pg_dump --format=custom --compress=6 --no-owner --no-privileges` |
| `storage.tar.gz` | 문서 저장소 전체 |
| `manifest.txt` | 백업 시각, 호스트, DB명, 파일 개수, 배포 커밋, 각 산출물 SHA-256 |

manifest 가 있어 **DB 덤프와 파일 세트가 어긋난 조합으로 복구되는 일**을 방지한다.

자동 실행: `/etc/cron.d/qa-manual-hub-backup` (기본 매일 02:30). 보존 정책은 `backup.sh` 의
`KEEP_DAILY`(기본 7), `KEEP_WEEKLY`(기본 4, 수동 승격), `KEEP_MONTHLY`(기본 3, 수동 승격) 변수로 조정.

**중요**: 백업이 원본과 같은 디스크에 있으면 디스크 장애 시 동시에 소실된다. `BACKUP_ROOT` 를
별도 볼륨/NAS 로 지정하거나 백업 디렉터리를 외부로 복제할 것을 권장.

## 복구 절차 (restore.sh)
<!-- akela: id=restore-procedure -->

```bash
sudo <APP_ROOT>/scripts/restore.sh <DATA_ROOT>/backup/20260827-023000
```

**현재 데이터를 대체하는 작업**이며 아래 순서로 안전 절차를 강제한다.

1. 무엇을 덮어쓸지 출력하고 `RESTORE` 타이핑을 요구 (`--yes` 로 생략 가능, 자동화 전용)
2. **현재 상태를 `backup/pre-restore-<timestamp>/` 에 먼저 백업** — 되돌릴 수 있음
3. 서비스 정지
4. `public` 스키마 DROP → CREATE → `pg_restore`
5. `storage` 를 `storage.replaced-<timestamp>` 로 옮기고 아카이브 전개
6. `alembic upgrade head` (덤프가 구버전 스키마일 수 있으므로)
7. 서비스 시작 및 `is-active` 확인
8. `qamh check-storage` 로 DB↔파일 일치 검증

문제가 없으면 `storage.replaced-*` 와 `pre-restore-*` 를 정리한다. 복구를 잘못했을 경우
`pre-restore-<timestamp>` 백업으로 다시 restore.sh 를 실행해 되돌린다.

## 설정 변경 시 함께 조정할 값
<!-- akela: id=config-coupling -->

- `MAX_UPLOAD_MB` 를 올릴 때는 nginx 의 `client_max_body_size` 도 함께 올려야 한다.
  nginx 가 앱보다 크게 잡혀 있어야 사용자가 기본 413 HTML 페이지 대신 앱의 한국어 안내
  메시지를 본다.
- `.env` 변경 후에는 `sudo systemctl restart qa-manual-hub` 필요.
- HTTPS 적용 시 nginx 에 `listen 443 ssl;` 블록 추가 + `.env` 의 `SESSION_COOKIE_SECURE=true`.
  애플리케이션 코드는 수정하지 않는다.

## 장애 확인 체크리스트
<!-- akela: id=troubleshooting-checklist -->

| 증상 | 확인 | 조치 |
|---|---|---|
| 502 Bad Gateway | `systemctl status qa-manual-hub` | 죽었으면 `journalctl -u qa-manual-hub -n 50`. `.env` 문법 오류가 흔한 원인 |
| 업로드 413 | 파일 크기 vs `MAX_UPLOAD_MB` / `client_max_body_size` | 두 값 모두 올리고 재시작 / 리로드 |
| 다운로드 410 Gone | `qamh check-storage` | DB 행은 있는데 파일 없음 → 백업에서 storage 복구 |
| 백업이 안 돎 | `tail <APP_ROOT>/logs/backup.log`, `systemctl status cron` | cron.d 파일 존재·권한(644) 확인 |
