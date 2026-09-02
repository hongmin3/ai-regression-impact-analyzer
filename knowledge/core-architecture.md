# 핵심 앱 — 구조와 경계

> 루트 `app/` 의 FastAPI 애플리케이션. 하위 서비스(`services/*`)는 별도 지식(`manual-hub-*.md`)을 쓴다.

## 계층 경계
<!-- akela: id=module-boundaries scope=core-development tier=must -->

- `app/core/` — 도메인에 독립적인 인프라만 둔다 (설정, 저장소, Gemini 클라이언트, 프롬프트 로더, 스케줄러, 업로드, 문서 캐시).
- `app/modules/<name>/` — 기능 하나가 자신의 router·schemas·서비스 로직·templates를 **전부 소유**한다.
- `app/web/router.py` — 어떤 모듈이 어떤 URL prefix를 쓰는지만 결정한다. **비즈니스 로직을 두지 않는다.**
- `app/prompts/` — 버전 관리되는 AI 프롬프트 YAML.
- 새 기능은 기본적으로 `app/modules/<name>/`에 추가한다. 별도 프로세스·별도 DB가 꼭 필요할 때만 `services/`를 만든다.

## Storage가 유일한 DB 접근 경로
<!-- akela: id=storage-single-owner scope=core-development tier=must -->

- `app/core/storage.py`의 `Storage` 클래스만 SQLite에 접근한다. 모듈이 테이블을 직접 조작하지 않고 명시적 메서드를 추가해 쓴다.
- 기능 전용 테이블은 `manual_*`처럼 충돌하지 않는 접두어를 쓴다. 공통 제품·문서는 기존 `products`/`documents`를 재사용한다.
- 스키마 변경은 `initialize()`의 `CREATE TABLE IF NOT EXISTS` + 컬럼 보강 방식이다. 반복 실행해도 안전해야 한다.

## 분석 대상 문서 선정 규칙
<!-- akela: id=active-documents-rule scope=core-development tier=must -->

- 검색 대상 문서는 `Storage.active_documents(kind, product)`로 가져온다 — 등록된 **모든** 문서가 항상 대상이다.
- 제품·버전당 최신 리비전 1개만 고르면 안 된다. 사양서1~5처럼 서로 다른 문서가 같은 제품·버전에 여러 개 등록될 수 있고, **새 문서가 이전 문서를 레거시로 만들지 않는다.**
- 이 규칙은 실제 오류에서 나왔다. `latest_documents` 방식으로 구현했다가 사용자 지적으로 뒤집혔다.

## 분석 작업 수명주기
<!-- akela: id=analysis-job-lifecycle scope=core-development tier=should -->

- 상태는 `QUEUED → RUNNING → DONE/FAILED`. 실행은 `Thread`로 띄우고 상태·단계는 `Storage.update_stage`/`update_analysis`로 기록한다.
- 동시 실행은 `analysis.max_concurrent_jobs`(기본 2)로 제한하고 초과 요청은 **429**로 거절한다.
- 프로세스 시작 시 `lifespan`에서 `fail_running_analyses()`로 재시작에 끊긴 RUNNING을 정리하고, 각 모듈의 `resume_queued_jobs()`로 QUEUED를 이어받는다. 새 모듈에 비동기 작업을 추가하면 이 두 가지를 함께 붙인다.
- `analysis.job_timeout_minutes` 동안 단계 갱신이 없는 RUNNING은 `/operations/status`에서 stale로 보고된다.

## 설정과 비밀정보
<!-- akela: id=settings-and-secrets scope=core-development tier=must -->

- 설정은 `config.yaml` 하나이며 `settings.get("a.b.c", default)`의 점 표기로 읽는다. 코드에 값을 하드코딩하지 않는다.
- 비밀정보 우선순위: OS 환경변수 > `secrets.json` > `secrets.txt` > `.env` > 코드 기본값.
- **비밀값 자체를 로그·화면·Report에 출력하지 않는다.** 외부에는 존재 여부·길이·출처 이름만 노출한다 (`/config/status`).
- 앱이 인식하는 키는 `app/core/secrets_loader.py`에 정의된 것뿐이다. 그 외 키는 앱 어디에도 노출되지 않는다.

## 문서 파싱 캐시
<!-- akela: id=document-cache scope=core-development tier=should -->

- 등록된 사양서·TC는 매 분석마다 다시 파싱하지 않는다. 파싱 결과를 `document_id` 기준으로 `storage.index_dir`에 JSON 직렬화해 재사용한다 (`app/core/document_cache.py`).
- BM25 인덱스는 캐시하지 않는다 — 재구성 비용이 파싱보다 훨씬 작다.
- 문서를 삭제하면 `document_cache.delete(document_id)`도 같이 호출해야 한다. 캐시가 남으면 삭제된 문서가 계속 검색된다.

## 검색 계층
<!-- akela: id=retrieval-protocol scope=core-development tier=should -->

- `app/retrieval/base.py`의 `Retriever` Protocol(`search(query, top_k)`)만 의존한다. 구현체는 `BM25Retriever`이며 제네릭이라 사양서 Chunk·TC·매뉴얼 항목에 그대로 쓴다.
- 검색 엔진을 바꾸려면 Protocol을 구현한 클래스를 추가하고 생성 지점만 교체한다. 호출부는 수정하지 않는다.

## 업로드 파일 취급
<!-- akela: id=upload-handling scope=core-development tier=should -->

- 업로드는 `app/core/uploads.py::save_upload`로만 저장한다. 확장자 허용 목록을 통과하지 못하면 400이다.
- 저장 파일명은 `uuid4().hex + 원래 확장자`다. 사용자가 준 파일명을 파일시스템 경로에 쓰지 않는다.

## 인앱 스케줄러
<!-- akela: id=in-process-scheduler scope=core-development tier=should -->

- 스케줄러는 uvicorn 프로세스 안에서 돈다. **신규 systemd 유닛을 만들지 않는다** — 서버 설정을 건드리지 않기 위한 결정이다.
- `app/core/scheduler.py`는 특정 job의 내용을 모른다. 각 모듈이 `register_scheduled_jobs(scheduler)` 콜백을 제공하고 `start_scheduler`가 그것을 실행한다. 새 정기 작업은 이 콜백에 붙인다.
