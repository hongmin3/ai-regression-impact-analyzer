# CLAUDE.md — qa-verification-management-system (QA 검증 관리 시스템)

SW 변경사항과 제품 사양서 및 Test Case를 분석하여 Regression 검증 대상을 자동 추천하는 QA 업무자동화 서비스

## Akela Context

Follow `akela/PROTOCOL.md` for every task.

## 저장소 구성 — 배포 단위 두 개

작업을 시작하기 전에 **어느 배포 단위를 건드리는지** 먼저 확인한다.

| | ① 핵심 앱 | ② 하위 서비스 |
|---|---|---|
| 위치 | `app/` (기능은 `app/modules/<name>/`) | `services/<name>/` |
| 스택 | FastAPI + Jinja2 + SQLite, 단일 uvicorn | 자체 스택 (예: React SPA + PostgreSQL) |
| 테스트 | 루트 `pytest` (`pytest.ini` testpaths=tests) | 자기 디렉터리에서 따로 실행 |
| CI | `.github/workflows/ci.yml` | `.github/workflows/<name>.yml` |

`services/*` 는 핵심 앱과 프로세스도 DB도 공유하지 않는다. 코드를 import 하거나 같은 DB를
읽는 방식으로 결합하지 않는다 — 연결은 URL 링크(`config.yaml` `services.*`)와 nginx
라우팅까지다. 어느 쪽에 기능을 추가할지 판단하는 기준과 체크리스트는
`docs/SHARED_PLATFORM_ARCHITECTURE.md` 에 있다.

Knowledge 는 하위 서비스도 루트 `knowledge/` 에 둔다 (`<name>-*.md`, `scope=<name>`).
`services/` 하위에 `akela.json` / `knowledge/` 를 새로 만들지 않는다.

## 문서

문서를 고치거나 추가할 때는 `docs/README.md`(문서 지도)의 표도 함께 갱신한다. 기능별 사용법은
문서가 아니라 앱 화면 안(`/impact-analyzer/guide`, `/manual-review/guide`)에 둔다.

## Project Root 탐색

이 프로젝트 하위 어디에서 작업하든(예: `src/`, `scripts/`, `tests/`) 먼저 현재 위치에서 상위로 `akela.json`을 탐색해 가장 가까운 Project Root를 식별하고, 그 Root의 `knowledge/`·`akela/PROTOCOL.md`를 사용한다. 하위 디렉터리에 별도 `akela.json`/`knowledge/`를 새로 만들지 않는다. 필요하면 `scripts/find-project-root.ps1`을 사용한다.

이 프로젝트를 Workspace 밖에서 단독으로 Clone해도 이 파일과 `akela.json`/`knowledge/`만으로 동일하게 동작해야 한다 (상위 Workspace 경로에 대한 의존성 없음).
