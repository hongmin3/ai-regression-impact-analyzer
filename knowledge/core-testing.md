# 핵심 앱 — 테스트 규칙

## 수집 범위
<!-- akela: id=test-scope scope=testing tier=must -->

- 루트 `pytest`는 `pytest.ini`의 `testpaths = tests`로 **핵심 앱 테스트만** 수집한다. `services/*`의 테스트는 자기 런타임(예: 실제 PostgreSQL)이 필요하므로 여기서 돌리지 않는다.
- 하위 서비스 테스트는 그 디렉터리에서 따로 실행하고, CI도 워크플로를 분리해 둔다.
- `tests/conftest.py`는 프로젝트 루트를 `sys.path`에 넣는 일만 한다. 무거운 fixture를 여기에 두지 않는다.

## 테스트는 API 비용을 발생시키지 않는다
<!-- akela: id=no-api-cost scope=testing tier=must -->

- Gemini 호출은 `responder` 콜백 주입으로 대체한다: `GeminiClient(storage=..., responder=lambda prompt: {...})`, `ImpactAnalysisAIClient(storage, responder=...)`.
- 실제 API Key를 읽거나 네트워크를 타는 테스트를 추가하지 않는다. 새 AI 클라이언트를 만들면 같은 `responder` 주입 지점을 제공한다.
- 캐시 동작을 검증할 때는 responder 호출 횟수를 센다 — 같은 prompt로 세 번 호출해도 responder는 두 번만 불려야 하는 식이다.

## 저장소는 임시 경로에 만든다
<!-- akela: id=storage-in-tmp scope=testing tier=should -->

- 테스트에서 `Storage(tmp_path / "test.db")`처럼 pytest `tmp_path`를 쓴다. 개발용 `data/app.db`를 건드리지 않는다.
- 업로드·인덱스·보고서 경로도 마찬가지다. 테스트가 `data/`나 `output/`에 파일을 남기면 안 된다.

## 실제 파일 E2E는 옵트인이다
<!-- akela: id=real-file-e2e-gate scope=testing tier=should -->

- 사내 기밀 문서를 쓰는 E2E는 Git 제외 대상인 `real_fixtures.local.env`에서 경로를 읽는다 (형식은 `real_fixtures.local.env.example`).
- 설정 파일이 없거나 경로에 접근할 수 없으면 **자동 skip**된다. GitHub Actions에서도 그대로 통과해야 한다.
- 사내망 서버 주소나 부서 폴더 체계를 테스트 코드에 하드코딩하지 않는다.

## CI 구성
<!-- akela: id=ci-split scope=testing tier=should -->

- `.github/workflows/ci.yml`(Core App CI)은 `services/**` 변경 시 돌지 않는다. `manual-hub.yml`은 그 반대다.
- 위생 검사 잡이 비밀·런타임 산출물이 커밋됐는지 `git ls-files`로 확인한다. 새로 만드는 런타임 디렉터리는 `.gitignore`와 이 검사에 함께 추가한다.
- 워크플로의 job 레벨 `env`에서는 `runner` 컨텍스트를 쓸 수 없다. 쓰면 워크플로 파일 자체가 유효성 검사에 실패해 잡이 하나도 실행되지 않는다.

## 회귀 테스트 통과가 배포 전제
<!-- akela: id=test-before-deploy scope=testing tier=should -->

배포 스크립트는 로컬 `pytest`를 먼저 통과시킨 뒤에만 파일을 서버로 복사한다. 테스트를 건너뛰고 배포하지 않는다.
