# 핵심 앱 — 배포와 운영

> 서버 주소·계정·경로 같은 사내 고유 정보는 여기에 적지 않는다. Git 제외 대상인
> `docs/local/OPERATIONS_LOCAL.md`에 둔다.

## 배포 스크립트가 옮기는 것
<!-- akela: id=deploy-script-scope scope=deployment tier=must -->

- `scripts/deploy.ps1`은 로컬 `pytest`를 통과시킨 뒤 `app`, `scripts`, `tests`, `config`, `docs`, `requirements.txt`, `config.yaml`, 예제 파일만 서버로 복사한다.
- `secrets.txt` / `secrets.json` / `.env` / `data/` / `output/`은 **복사하지 않는다.** 서버의 실제 설정과 운영 데이터를 덮어쓰지 않기 위한 의도적 설계다.
- 서버 배포 폴더는 Git 저장소로 두지 않는다. 로컬에서 검증한 파일만 옮긴다.
- `config.yaml`은 복사 대상이다. 서버에만 있는 설정 차이를 만들면 다음 배포에서 덮어써진다 — 그런 값은 환경변수나 `secrets.*`로 빼야 한다.

## 의존성 동기화는 따로 한다
<!-- akela: id=dependency-sync scope=deployment tier=must -->

`deploy.ps1`은 파일만 복사하고 `pip install`을 실행하지 않는다. `requirements.txt`가 바뀌었으면 배포 후 서버에서 `.venv/bin/pip install -r requirements.txt`를 반드시 실행한다. 빠뜨리면 새 패키지가 없어 앱이 뜨지 않는다.

## 재기동 절차
<!-- akela: id=restart-procedure scope=deployment tier=must -->

- 핵심 앱은 같은 포트를 쓰는 기존 프로세스를 종료한 뒤 `nohup ... uvicorn app.main:app --host 0.0.0.0 --port <port>`로 다시 띄운다.
- 재기동 후 `/health`가 `{"status":"ok"}`를 반환하는지, 주요 화면(`/`, `/knowledge`, `/analyses`)이 뜨는지 확인한다.
- **다른 서비스나 포트는 건드리지 않는다.**

## 같은 호스트의 다른 서비스를 보호한다
<!-- akela: id=host-isolation scope=deployment tier=must -->

- 이 프로젝트가 설치하지 않은 systemd 유닛·nginx 사이트·PostgreSQL 설정은 변경하지 않는다. 이 프로젝트의 것만 추가하거나 갱신한다.
- 배포 대상 디렉터리 밖의 파일은 열람·수정하지 않는다.
- 방화벽은 이 프로젝트가 쓰는 포트를 여는 등 범위 내 변경만 한다.
- 서버 등록·설정 변경은 영향 범위를 사용자에게 확인한 뒤 진행한다.

## 하위 서비스 통합 배포
<!-- akela: id=platform-nginx scope=deployment tier=should -->

- 같은 호스트의 nginx가 `/`는 핵심 앱(:12000)으로, `/manual-hub/`는 하위 서비스로 라우팅한다 (`deploy/nginx/qa-platform.conf`).
- 하위 서비스 프론트엔드를 재배포할 때 **반드시 `BUILD_MODE=platform`**을 준다. 빠뜨리면 단독용(base `/`)으로 빌드돼 화면이 빈 채로 뜬다. `deploy.sh`가 전송 전에 검사해 중단시킨다.
- 하위 서비스의 `install.sh`를 다시 돌릴 일이 있으면 `SKIP_NGINX=1`을 준다. 안 주면 단독용 nginx 사이트가 다시 설치돼 `/`가 하위 서비스로 돌아간다.
- 통합 전 주소를 쓰던 북마크를 위해 nginx가 구 경로를 `/manual-hub/*`로 301 리다이렉트한다. 핵심 앱에 그 이름들과 겹치는 경로를 만들면 이 블록을 먼저 정리해야 한다.

## 점검 순서
<!-- akela: id=check-order scope=deployment tier=should -->

Health endpoint → app.log → 입력 형식 → TC ID 컬럼 → `.env` Key → Gemini Rate Limit/Timeout → 검색 Chunk 존재 여부 순서로 확인한다.

## 백업과 상태 확인
<!-- akela: id=ops-monitoring scope=deployment tier=should -->

- `/operations/status`가 실행 중·대기 중 작업 수와 stale 작업을 보고한다. `analysis.job_timeout_minutes` 동안 단계 갱신이 없으면 stale이다.
- SQLite 백업은 Online Backup + SHA-256 + 임시 복원 무결성 검증까지 수행한다 (`scripts/backup_data.py`).
- 상세 절차는 `docs/OPERATIONS.md`에 있다.
