# Next Steps — 매뉴얼 개정 검증 기능 진행 상황 (우선순위 순)

## 2026-09-02 운영 신뢰성·평가·CI·백업·PDF 개정 표시 고도화

- 분석 동시 실행 제한, 요청 원본 경로 보존, 재실행 API/UI, 재시작 후 QUEUED 작업 자동 복구.
- `/operations/status`와 CLI 모니터, SQLite Online Backup+SHA-256+임시 복원 무결성 검증.
- QA 정답 기반 precision/recall/F1 평가 CLI와 GitHub Actions 전체 pytest/추적 파일 검사.
- PDF vector line과 텍스트 span의 위치를 대조해 취소선·밑줄을 보수적으로 판독. 취소선 근거는
  자동으로 Human Review가 필요하며, 애매하거나 이미지 기반인 경우 기존처럼 `UNVERIFIED` 유지.
- Windows `AIRegressionAnalyzer_VXvueSpecSync` Action을 현재 프로젝트 경로로 수정하고 dry-run 성공 확인.
- 기능 커밋 `7d8f854`, pytest 격리 커밋 `611e4a9` push 및 GitHub Actions 성공. 로컬
  `209 passed`, 원격 `211 passed, 1 skipped`. 운영 포트 12000 PID `1294165` → `1297440`,
  주요 6개 페이지 200과 보호 대상 서비스 PID 불변 확인.
- 운영 smoke 백업 17개 파일의 SHA-256·SQLite 임시 복원 검증 통과. 사용자 crontab에 매일
  02:15 백업과 10분 간격 모니터를 추가했으며 기존 다른 서비스 cron은 그대로 보존했다.

> **2026-09-02 완료 확인**
> - 로컬 폴더 rename(`qa-verification-management-system`)과 Windows 작업 스케줄러
>   `AIRegressionAnalyzer_VXvueSpecSync`의 경로 갱신을 사용자가 세션 밖에서 직접 완료했음을
>   `pwd`·`Get-ScheduledTask`로 확인했다 (`HANDOFF.md` §2 참고).

## 2026-09-02 등록 문서 파싱 결과 캐시

- Knowledge 등록 시 사양서 Chunk·전체 원문과 TC 파싱 결과를 `document_id` 기준으로 저장한다.
- 제품 분석은 캐시를 우선 사용하고, 기존 등록 문서처럼 캐시가 없거나 JSON이 손상된 경우에만
  원본 PDF/DOCX/XLSX를 다시 파싱한 뒤 캐시를 자동 복구한다.
- 문서 삭제 시 해당 JSON·원문 캐시도 함께 삭제한다. 캐시 저장/삭제 실패는 보조 성능 기능의
  문제이므로 문서 등록·분석·삭제 본 작업을 실패시키지 않는다.
- BM25 객체 자체는 라이브러리 버전 호환 문제를 피하기 위해 직렬화하지 않고, 캐시된 Pydantic
  데이터에서 매번 가볍게 재구성한다.
- 커밋 `c60380c`·push·운영 배포 완료. 로컬 `201 passed`, 원격 `200 passed, 1 skipped`,
  포트 12000 PID `1262810` → `1294165`로 재기동했다. 주요 6개 페이지가 모두 200이고 다른
  보호 대상 포트의 PID는 배포 전과 동일함을 확인했다.

## 2026-09-01 TC 컬럼/시트 수동 매핑 UI (`HANDOFF.md` §5 4번, MVP 최초 커밋부터 9개월 미착수)

TC Excel의 헤더가 별칭 목록(`app/parsers/excel_parser.py::ALIASES`)에 없어 TC ID 컬럼을
자동으로 못 찾으면, 이전에는 업로드는 조용히 성공하고 한참 뒤 분석 실행 시점에야
`ValueError`로 실패가 드러났다(원인 파악 방법이 "TC 파일을 다른 헤더명으로 재작성"뿐).

- `app/parsers/excel_parser.py`: `parse_testcases(path, mapping=None, sheet_name=None,
  header_row=None)` — `sheet_name`+`header_row`를 둘 다 주면 자동 탐지를 건너뛰고 그 위치를
  강제 사용(실패 시 다른 시트로 넘어가지 않고 즉시 에러 반환). `suggest_columns(headers)`(예외
  없이 컬럼 인덱스→필드 추정), `preview_workbook(path)`(시트별 상위 15행 미리보기) 추가.
- `app/modules/knowledge/router.py`: `register_testcase`가 업로드 시점에 `parse_testcases`를
  실제로 호출해 검증한다(이전에는 저장만 하고 끝). 실패하면 `/knowledge/testcase/map`으로
  리다이렉트 — 시트/헤더 행을 선택하면(GET) 그 행의 실제 셀 값으로 8개 필드(TC ID 필수 등)
  드롭다운을 보여주고(별칭 매칭되는 값은 미리 선택), 확정하면(POST) 매핑을 검증 후
  `documents.metadata_json`에 `column_mapping`/`sheet_name`/`header_row`로 저장한다.
- `regression_analyzer.py::run_for_product`가 TC 문서의 저장된 metadata를 읽어
  `parse_testcases`에 그대로 전달 — 매핑이 없는(기존) 문서는 지금처럼 완전 자동 탐지 그대로
  동작해 하위 호환 유지.
- 알려진 제약(v1): 같은 헤더 텍스트가 같은 행에 중복되면 첫 번째 열만 매핑된다(값 자체로
  대조하는 방식의 한계, 필요시 인덱스 기반 매핑으로 확장 검토).
- 테스트 13건 추가(`test_excel_parser.py`, 신규 `test_knowledge_testcase_mapping.py`) —
  `pytest -q` **196 passed**. 실제 로컬 서버에 업로드→매핑→등록 전체 흐름 수동 검증(생성한
  테스트 제품/문서는 검증 후 정리 완료).
- 커밋(`4459dd3`)·push·배포 완료. 원격 `195 passed, 1 skipped`, 포트 12000만 PID `1261121`
  → `1262810`으로 재기동, 다른 포트 PID 그대로 유지, 주요 6개 페이지 200 확인.

## 2026-09-01 분석 이력 검색·필터·페이지네이션 (`/analyses`)

- `Storage.list_analyses`: `status`/`product`/`search`(ID·변경 문서명 부분일치) 필터와
  `limit`/`offset` 페이지네이션 추가, 반환값을 `(행 목록, 필터 적용 후 전체 건수)`로 변경
  (기존 유일한 호출부인 `impact_analyzer/router.py`도 함께 갱신). `product` 필터는 전용
  컬럼이 없어 `request_json`을 `json_extract`로 대조한다(SQLite JSON1, 이 환경에서 동작 확인).
- `/analyses` 라우트에 `status`/`product`/`q`/`page` 쿼리 파라미터 추가, 페이지 크기 25.
  `analyses.html`에 검색창·상태/제품 드롭다운·이전/다음 페이지 링크 추가(필터 값은 페이지
  이동 시에도 유지).
- 테스트 7건 추가(`test_persistent_analyses.py`) — `pytest -q` **183 passed**(real-file E2E
  제외 기준). 실제 로컬 서버 데이터(분석 9건, DONE 5건)로 필터·검색·빈 결과 모두 확인.
- 커밋(`7b38ac5`)·push·배포 완료. 원격 `183 passed, 1 skipped`, 포트 12000만 PID `1260054`
  → `1261121`로 재기동, 다른 포트 PID 그대로 유지, `/analyses?status=DONE&page=1` 포함
  주요 페이지 200 확인.

## 2026-09-01 매뉴얼 개정 검증 캐시 Hit 기록 추가 (비용 대시보드 v1 공백 해소)

비용 대시보드에서 드러난 공백 — `impact_analyzer`만 `ai_audit.cache_hit`을 기록해 매뉴얼 개정
검증은 캐시 통계에서 빠져있던 문제를 해결했다.

- `app/core/gemini_client.py`: `cache_hit_count` 누적 카운터 추가. 캐시 Hit 시 `_request()`를
  호출하지 않고 즉시 반환하도록 재구성해, **캐시 Hit은 실제 비용이 0이므로 `token_usage`에
  다시 합산하지 않도록 수정**(부수적으로 발견한 버그: 이전에는 캐시로 재사용해도 원래 호출의
  토큰 수가 다시 집계되어 `daily_token_limit`을 실제보다 과다 소모한 것처럼 보이게 했다).
  `token_usage`는 이제 이 클라이언트 인스턴스가 실제로 과금된 호출만 누적한다(매뉴얼 개정
  검증처럼 한 인스턴스로 변경 건마다 여러 번 호출하는 경우도 정확히 합산됨 — 기존에는 마지막
  호출값으로 덮어써져 과소집계되는 별개의 버그가 있었다).
- `ManualReviewAIClient.cache_hit_count` 프로퍼티 추가, `reviewer.py`의 두 결과 조립 지점에
  `"ai_audit": {"request_count": ..., "cache_hit_count": ...}` 추가.
- `Storage.cost_dashboard_stats`: `ai_audit.cache_hit`(bool, impact_analyzer)와
  `ai_audit.cache_hit_count`/`request_count`(누적, manual_review) 두 형태를 모두 처리하도록
  일반화(`_cache_calls_from_audit`). 집계 단위가 "분석 건수"에서 "Gemini 호출 건수"로
  바뀌었다(대시보드 UI 문구도 갱신).
- 테스트 4건 추가/보강(`test_gemini_and_report.py`, `test_manual_review_reviewer.py`,
  `test_cost_dashboard.py`) — `pytest -q` **178 passed**. 실제 로컬 서버 렌더링도 재확인.
- 커밋(`af0287a`)·push·배포 완료. 원격 `177 passed, 1 skipped`(real-file E2E는 예상대로
  skip), 포트 12000만 PID `1258104` → `1260054`로 재기동, 다른 포트(5000/5001/5002/5003/
  8000/10000/18800) PID 그대로 유지, 주요 6개 페이지 200 확인.

## 2026-09-01 실제 파일 기반 E2E pytest 편입 (OPEN_QUESTIONS.md #5 완료)

`tests/test_manual_review_real_files_e2e.py` 신규 추가 — 상세 내용은 `OPEN_QUESTIONS.md` #5
참고. 요약: 고정 경로 참조 + skip 방식으로 결정, 경로 자체는 `.deploy.env`와 동일하게
`real_fixtures.local.env`(Git 제외)로 분리해 공개 repo에 사내망 IP/부서 폴더 체계를
노출하지 않는다. `pytest -q` **175 passed** (이 PC 기준 약 80초, 경로 미설정 환경에서는
skip되어 기존과 동일하게 빠름). 커밋(`458dbd3`)·push·서버 배포 완료 — 원격은 예상대로
`174 passed, 1 skipped`(13.75초, 기존과 동일), 포트 12000만 PID `1255193` → `1258104`로
재기동, `/health` 및 주요 6개 페이지 200 확인. 다른 포트(5000/5001/5002/5003/8000/10000)
PID 그대로 유지 확인. 포트 18800(`/opt/ai-remote-hub`, 별도 프로젝트)만 PID가 바뀌어
있었으나 uptime이 이번 재시작 시점보다 훨씬 이전이라 이 세션의 조작과 무관하게 자체
재기동된 것으로 확인(정상 응답 200, 추가 조치 안 함).

## 2026-09-01 비용/캐시 대시보드 UI 구현

"아직 미착수" 3번 항목(비용/캐시 대시보드 UI)을 구현했다.

- `analyses` 테이블에 `module` 컬럼 추가(`ALTER TABLE`, 기존 배포와 호환). `create_analysis()`가
  `module="impact_analyzer"`/`"manual_review"`를 명시적으로 기록해 이후 통계에서 기능별로 구분
  가능. 이 컬럼이 없던 과거 행은 `result_json`에 `revision_id` 키가 있는지로 `manual_review`
  여부를 추정해 하위 호환을 유지한다(`Storage.cost_dashboard_stats`).
- 신규 `Storage.cost_dashboard_stats(days=30)`: 토큰/캐시 전용 컬럼이 없으므로 `result_json`을
  런타임 파싱해 일별 토큰 합계, 기능별(Regression 영향 분석/매뉴얼 개정 검증) 토큰·건수, 캐시
  Hit율, 최근 50건 목록을 계산한다. 데이터量이 현재 매우 적어(실서버 완료 분석 5건) 성능 문제
  없음을 확인.
- **알려진 v1 범위(버그 아님)**: 캐시 Hit 여부는 Regression 영향 분석의 `ai_audit.cache_hit`만
  기록하고 있어 매뉴얼 개정 검증은 캐시 통계에서 제외된다(대시보드 화면에 안내 문구 표시).
  `ai_cache` 테이블 자체에 재사용 횟수 카운터가 없어 "몇 번 재사용됐는지"는 계산 불가.
- 신규 모듈 `app/modules/cost_dashboard/`(`/cost-dashboard`): 오늘 토큰 한도/사용량(기존
  `daily_token_status()` 재사용), 조회 기간(7/30/90일), 기능별 사용량, 캐시 Hit율, 일별 토큰
  사용량(막대), 최근 분석 50건 표를 표시. 기존 3개 모듈의 nav에 링크 추가, hub 카드는 추가하지
  않음(Knowledge와 동일하게 nav 전용 운영 페이지로 취급).
- 테스트 7건 추가(`tests/test_cost_dashboard.py`) — `pytest -q` **174 passed**. 실제 로컬 서버로
  기존 완료 분석 5건(합계 313,844 tokens) 렌더링까지 확인.
- 커밋(`c674185`)·GitHub push·`scripts/deploy.ps1` 배포 완료. 원격 `pytest -q` 174 passed,
  구 PID `1253849` → 신 PID `1255193`로 포트 12000만 재기동, 다른 포트(5000/5001/5002/5003/
  8000/10000/18800)는 PID 그대로 유지 확인. `/health` 및 `/`, `/impact-analyzer`,
  `/manual-review`, `/knowledge`, `/cost-dashboard`, `/analyses` 전부 200 확인.

## 2026-09-01 Cross-Manual/이미지 Gate 마무리 + 명칭 통일 (로컬 폴더 rename만 미완료)

이전 세션이 미완료 상태로 남긴 작업을 이어받아 완료했다. 이 절 아래 두 하위 절
("현재 작업 인계"/"사용자 최신 명칭 요청")은 인계 당시 상태를 그대로 남겨두고, 완료 결과는
이 절 본문에 정리한다.

- **테스트 fixture 수정 완료**: 합성 PNG의 zlib checksum이 잘못돼 PyMuPDF `insert_image`가
  `FzErrorLibrary: zlib error: incorrect data check`를 던졌다. `zlib.compress`로 올바르게
  생성한 1x1 RGB PNG bytes로 교체 — 전체 `pytest -q` **167 passed**.
- **코드 리뷰 완료**: `cross_manual.py`, `docx_track_changes.py`(이미지 감지),
  `pdf_revision_diff.py`(이미지 hash), `reviewer.py`(6단계 파이프라인), `storage.py`
  (`manual_cross_impacts`), `router.py`/`revision.html`(QA 확정 UI) 통합 상태 확인.
  `git diff --check` 통과(CRLF 변환 경고만 있고 실제 whitespace 오류 없음).
- **문서 갱신 완료**: `README.md`를 AI 비용 절감 아키텍처 중심으로 재작성, `HANDOFF.md`에
  3~7차 세션 요약 추가.
- **명칭 통일**: 표시명 **QA 검증 관리 시스템**, GitHub repo slug
  **qa-verification-management-system**으로 변경 완료(origin도 갱신). 원격 Ubuntu 배포
  경로는 운영 중인 서비스라 의도적으로 이전 이름 유지.
- **미완료: 로컬 폴더 rename**. 이 작업을 수행한 Claude Code 세션 자신이 폴더를 작업
  디렉터리로 물고 있어 세션 내부에서는 구조적으로 rename이 불가능했다(다른 창을 다 닫아도
  동일한 `used by another process` 오류 재현). 이 세션 창을 닫은 뒤 사용자가 직접 실행해야
  하며, 함께 갱신해야 하는 Windows 작업 스케줄러(`AIRegressionAnalyzer_VXvueSpecSync`) 경로
  포함 정확한 명령은 `HANDOFF.md` §2에 정리했다.
- Akela run `core-development-manual-image-change-human-review-gate-d240e7`은 applied
  source 기록 후 outcome DONE으로 닫았다.
- 배포·검증 완료: `scripts/deploy.ps1`로 서버 반영, 원격 `pytest -q` 167 passed, 포트 12000
  프로세스만 재시작 후 `/health` 및 주요 7개 페이지 200 확인, 다른 포트(5000/5001/5002/5003/
  8000/10000/18800) 서비스는 그대로 유지됨을 확인.

### (인계 당시 기록) 2026-09-01 현재 작업 인계 (커밋 전)

현재 작업 트리는 **의도적으로 미완료 상태**이며 되돌리면 안 된다. 마지막 커밋은
`64ab206`, 마지막 기능 커밋은 `516c308`(Regression 분석 상세 감사 기록)이다.

- 완료·배포됨: 분석 이력 행을 누르면 요청 문서, Knowledge 문서, System Instruction,
  Gemini 실제 입력 JSON/원본 응답, 모델/캐시/생성 설정, BM25 후보 순위와 점수를 보는 상세 화면.
- 실제 서버 완료 분석 표본은 1건: 전체 TC 6,407 / AI 후보 150 / 최종 추천 3. 표본 부족으로
  `retrieval.candidate_limit=150`은 변경하지 않았다.
- 구현 완료 후 테스트 통과했던 작업: Cross-Manual 영향분석. 같은 제품의 다른 매뉴얼 최신
  리비전(없으면 Knowledge 문서)을 Release/설계 변경과 BM25 대조하고 DB에 저장하여 결과
  화면에서 QA가 확인 필요/영향 있음/영향 없음으로 확정한다. 이 시점 테스트는 165 passed였다.
- 현재 진행 중: 이미지 변경 Human Review Gate. DOCX Track Changes 내부 drawing/pict 및 PDF
  페이지 이미지 hash 변화를 감지해 `IMAGE_CHANGE_REVIEW_REQUIRED`로 강제하는 코드가 작성됐다.
- 현재 전체 테스트: **166 passed, 1 failed**. 실패는 기능 코드가 아니라
  `tests/test_pdf_revision_diff.py::test_pdf_image_change_is_detected_and_requires_review`의 합성 PNG
  fixture가 PyMuPDF에서 `zlib error: incorrect data check`를 내는 문제다. 유효한 PNG fixture를
  표준 라이브러리로 생성하거나 검증된 작은 PNG bytes로 교체한 뒤 전체 테스트를 다시 실행한다.
- 아직 커밋/푸시/배포하지 않았다. 수정 목록은 `git status --short`로 확인한다.
- 활성 Akela run: `core-development-manual-image-change-human-review-gate-d240e7`. 작업 완료 후
  applied source와 outcome DONE을 기록한다.

사용자 최신 명칭 요청:

- 문서 표시명: **QA 검증 관리 시스템**
- 제안한 GitHub repo/local folder slug: `qa-verification-management-system`
- 아직 rename하지 않았다. 이미지 Gate 테스트를 먼저 정상화하고, 전체 Markdown/README/설정의
  이전 이름과 절대경로를 갱신한다. README에는 AI API 토큰 절감 설계(BM25/RAG Top-K,
  Rule prefilter, 후보 150 상한, 2단계 quick/detail, PASS 상세 호출 생략, SHA-256 cache,
  Structured Output 1회 호출, thinking_budget=0, 일일 토큰 한도)를 중심으로 설명한다.
- 그 다음 `gh auth status` 확인 → GitHub repo rename → `origin` URL 확인 → 프로젝트 폴더 rename
  순으로 수행한다. 폴더 rename 후 `akela.json`, AGENTS 탐색과 모든 배포 경로가 새 루트에서
  정상인지 반드시 확인한다.

## 2026-09-01 세션에서 완료

**3차 (QA 플랫폼 허브)**: 루트(`/`)를 공용 QA 자동화 허브로 전환하고 기존 Regression
분석 시작 화면을 `/impact-analyzer`로 분리했다. `/manual-review`와 함께 두 기능을 카드로
선택할 수 있으며, 기존 `/analyses`·`/knowledge`·동기화 API 경로는 호환성을 유지한다.
공유 DB와 새 QA 모듈의 확장 원칙은 `docs/SHARED_PLATFORM_ARCHITECTURE.md`에 정리했다.
로컬/서버 `pytest -q` 132건 통과 후 실서버 재배포·재기동과 주요 6개 페이지 200 응답까지
검증했다.

**4차 (공용 Knowledge + 이전 Comment 반영 참고 판정)**: 사양서·TC 관리 기능을
`app/modules/knowledge/` 독립 모듈로 분리해 회귀 분석과 매뉴얼 검증이 함께 사용하도록
재구현했다. 매뉴얼 화면에서 제품별 SRS 파일명·등록 시각·최근 동기화 상태를 확인하고 공용
Knowledge에서 추가·삭제할 수 있다. 이전 Round의 미해결 Comment는 전체 조상 계보에서
이어받고, 현재 Track Changes와 로컬 유사도를 비교해 `반영 의심/미반영 의심/판단 불가`를
참고 표시한다. QA가 `해결/미해결/재오픈/제외`를 확정하기 전에는 상태를 자동 변경하지 않는다.

**5차 (PDF 매뉴얼 리비전 diff)**: 첫 PDF를 Baseline으로 등록하고 다음 PDF부터 이전 PDF를
선택해 페이지별 텍스트 추가·삭제·수정을 추출한다. PDF 변경은 위치/레이아웃 해석 오차를
감안해 AI confidence를 최대 60%로 제한하고 모든 항목에 `PDF_DIFF_REVIEW_REQUIRED`를
표시한다. PDF에는 Word Comment를 생성하지 않으며 QA가 결과 화면에서 직접 최종 판정한다.

**6차 (Release/설계검토 상세 근거)**: Release Note의 `Description for Each Version`에서
기존 항목의 Before/Now 상세 설명을 추출해 중복 항목 없이 검색과 AI 보조 근거에 추가한다.
설계검토보고서의 변경 결과 절에서 Pass/Fail을 문제 분석 제목과 연결하며, Fail 항목은 서버가
`DESIGN_REVIEW_FAILED`와 Human Review 필요 상태를 강제한다. 최종 기능 사실 판단은 계속
SRS를 최우선으로 한다.

**1차 (스켈레톤 → 동작하는 파이프라인)**: 코드 구조 리팩터링(`app/core/`·`app/prompts/`·
`app/modules/{impact_analyzer,manual_review}/`·`app/web/`), DOCX Track Changes 파서,
NON_FUNCTIONAL_CHANGE 필터, SRS 근거 로컬 검색(impact_analyzer가 이미 관리하는 등록 사양서
재사용), 2단계 AI 판정 파이프라인, 업로드/SSE/결과 화면/QA Override, Word Comment 자동 삽입
(`python-docx` 추가).

**2차 (Release Note/설계검토보고서 파서 + Reverse 검증)**: 사용자가 실제 VXvue 1.1.0 예시
파일(Release Note, 설계검토보고서, Round 1 매뉴얼, 기준 사양서)을 제공해 실제 문서로 검증하며
아래를 구현·수정했다.

- ✅ `release_scope.py`: Release Note의 Added/Changed/Fixed bug/Etc 카테고리 헤더 인식,
  설계검토보고서의 "문제 분석" 절 번호 매김 항목(N.N.N) 추출. **실제 문서로 검증하며 발견한
  버그 다수 수정**: 문서 앞머리 메타데이터 표 노이즈 제외, TOC(목차) 점선 리더 항목이 실제
  섹션 헤더와 문구가 같아 조기 종료되던 문제, 다음 대분류 절이 같은 N.N.N 번호를 재사용해
  항목이 중복 수집되던 문제, "Etc (내부 배포용 – ...)" 처럼 괄호 부연이 붙은 헤더 인식.
- ✅ Reverse 검증(누락 의심, 스펙 §13): Release Scope 항목을 이번 리비전의 functional 매뉴얼
  변경과 BM25로 대조해 매칭 안 되면 `manual_release_findings` 테이블에 MISSING_SUSPECTED로
  저장. reviewer 파이프라인에 "Release Scope 대조" 단계 추가(5단계로 확장), 결과 화면에
  "누락 의심" 섹션 표시.
- ✅ 업로드 폼에 Release Note/설계검토보고서 선택적 첨부 추가 — 미첨부 시 해당 제품에 이미
  등록된 최신 문서를 자동 재사용(`documents` 테이블의 `release_note`/`design_review` kind로
  재사용, 신규 스키마 변경 없음).
- ✅ **실제 파일로 전체 파이프라인 E2E 검증 완료**: 실제 VXvue Service Manual Round 1(.docx,
  799건 변경, 704건 functional) + 실제 Release Note(68건) + 실제 설계검토보고서(40건) +
  실제 등록 사양서(SRS)로 `ManualRevisionReviewer.run()`을 끝까지 실행(mock AI 사용, 42초),
  Release Scope 108건 중 102건 FOUND·6건 MISSING_SUSPECTED — 결과가 실제로 QA가 확인해볼
  만한 합리적인 항목들로 확인됨.
- ✅ 테스트 19건 추가 (`test_release_scope.py` 15건 + reviewer/router 통합 4건), 전체
  `pytest -q` **130 passed**.
- ✅ (사용자 요청) 모든 코드는 특정 제품명을 하드코딩하지 않도록 점검·수정 — 추후 VXvue 외
  제품 확장을 염두에 둔 설계 유지(`comment_writer.py`의 author를 `{product} QA AI`로 조립).

## 2026-09-02 운영 자동 복구 · 전체 경로 감시 · 매뉴얼 서버 데이터 연동

미착수 목록의 1·2·3·7번을 처리했다.

- **1. systemd 전환 완료.** 핵심 앱이 `nohup` 프로세스로만 떠 있어 재부팅에서 살아남지
  못하던 문제. `deploy/systemd/qa-verification.service` 를 추가하고 실서버에 설치·enable
  했다. 검증: `systemctl restart` 정상, `kill -9` 후 자동 복구(MainPID 1307421 → 1307442),
  로그가 기존 `output/logs/uvicorn.out` 에 계속 기록. 다른 서비스 포트 PID 전부 유지.
- **2. 모니터 확장 완료.** `--check NAME=URL` 을 추가해 nginx 와 매뉴얼 서버까지 감시한다.
  조회 실패가 traceback 이 아니라 alert 로 나오도록 고쳤고, operations 조회가 실패하면
  근거 없이 무결성/stale 판정을 내리지 않는다. 테스트 7건.
- **3. cron 정리 완료.** 조사 중 **모니터가 16번 실행됐지만 매번 실패**하고 있던 것을
  발견했다 — crontab 줄 끝에 리터럴 `
`(0x5C 0x72)이 붙어 리다이렉트가 깨져 `monitor.log`
  가 아예 생성되지 않았다. 오염을 제거하고, 서버 TZ 가 `America/New_York` 이라 02:15/02:30
  이 실제로는 15:15/15:30 KST 였던 것도 14:15/14:30 EDT(= 03:15/03:30 KST)로 옮겼다.
  `jjhhub` 등 다른 서비스의 cron 줄은 그대로 보존. 갱신 후 cron 이 실제로 로그를 남기는
  것까지 확인했다(`{"status": "ok", ..., "checks": {"nginx": "ok", "manual_hub": "ok"}}`).
- **7. 매뉴얼 서버 데이터 연동 완료(기본 비활성).** Cross-Manual 대조 대상을 (1) 로컬 최신
  리비전 → (2) 매뉴얼 서버 Current → (3) Knowledge 문서 순으로 모은다. `app/core/
  manual_hub_client.py` 는 HTTP API 만 사용하며 매뉴얼 서버 코드·DB 를 직접 건드리지
  않는다. 장애 격리 테스트가 실제 결함을 잡았다 — `from_settings()` 가 try 밖에 있어 설정
  로딩 실패가 검증 전체를 죽였다. 테스트 15건, `pytest -q` **236 passed**.

**7번 연동 실서버 활성화 완료 (2026-09-02).** 사용자가 매뉴얼 서버에 전용 계정을 만들고
서버 `secrets.txt` 에 자격증명을 넣었으며, `config.yaml` 의 `api_url` 은
`http://127.0.0.1/manual-hub/api`(같은 호스트 nginx 경유)로 설정했다.

실서버 검증 결과:

- 연동 활성화 `예`, 매뉴얼 서버 로그인 성공, 제품 2개(`Bellalun Viewer`, `VDMS-1100TM`) 조회.
- `Bellalun Viewer` 대조 소스 2건 확보 — Operation Manual(V1.0.12W1, 18.8MB),
  DICOM Conformance Statement(V1.3W1, 343KB). 검증 대상 매뉴얼 자신은 제외됨.
- 주요 9개 경로 200, 다른 서비스 포트·유닛 전부 유지, 앱 로그 오류 0건,
  모니터 `{"checks": {"nginx": "ok", "manual_hub": "ok"}}`.

실제 데이터로만 드러난 문제 두 가지를 함께 고쳤다. (1) 매뉴얼 서버는 Revision/Version
형식을 강제하지 않아 실제 문서의 `current_revision` 이 비어 있었다 — Revision → Version →
출처 순으로 라벨을 채운다. (2) 매 검증마다 18.8MB 를 다시 내려받고 있었다 — 파일명에
version id 를 넣어 같은 Current 는 로컬 사본을 재사용하고, 바뀌면 새로 받으며 지난 사본을
지운다.

**남은 제약**: 연동은 제품 **이름**으로 매칭한다. 현재 겹치는 제품은 `Bellalun Viewer`
하나뿐이고, 핵심 앱의 `VXvue` 는 매뉴얼 서버에 같은 이름의 제품이 없어 조용히 건너뛴다
(오류 아님). VXvue 매뉴얼도 대조에 쓰려면 매뉴얼 서버에 `VXvue` 제품을 만들고 매뉴얼을
등록해야 한다.

## 아직 미착수 (2026-09-02 재정리, 우선순위 순)

앞선 항목들(Cross-Manual, 이미지 Gate, 비용 대시보드, 실파일 E2E)은 모두 완료됐다. 저장소
병합과 `/manual-hub` 통합 이후 기준으로 다시 정리한다. 각 항목의 "확인" 줄은 2026-09-02에
실서버에서 직접 확인한 근거다.

### A. 운영 리스크 — 먼저 손봐야 하는 것

1. ~~**핵심 앱이 서버 재부팅 시 자동으로 뜨지 않는다.**~~ → 완료 (위 참고). systemd 유닛도 `@reboot` cron도 없고
   `nohup` 프로세스(PPID 1)로만 떠 있다. 매뉴얼 서버는 `qa-manual-hub.service`가 enabled라
   자동 복구되는데 핵심 앱만 수동 재기동이 필요하다. 현재 서버 uptime이 7주라 아직 겪지
   않았을 뿐이다. `docs/DEPLOYMENT.md` §5에 유닛 예시가 이미 있다.
   - 확인: `/etc/systemd/system`에 관련 유닛 없음, `crontab -l`에 `@reboot` 없음,
     `ps -o ppid` = 1.
2. ~~**모니터링이 핵심 앱만 본다.**~~ → 완료 (위 참고). `scripts/monitor_health.py`가 10분마다 `127.0.0.1:12000`만
   확인한다. 통합 이후 실제 사용자 진입점은 nginx(:80)이고, 매뉴얼 서버(:9180)와
   PostgreSQL은 감시 대상이 아니다. `/manual-hub/api/health`와 nginx를 감시 대상에 추가해야
   한다.
3. ~~**백업이 한국 업무시간에 돈다.**~~ → 완료 (위 참고). 서버 타임존이 `America/New_York`이라 cron의 02:15 /
   02:30이 실제로는 **15:15 / 15:30 KST**다. 지금은 DB 덤프 40K + 저장소 48M이라 영향이
   작지만, 매뉴얼이 쌓이면 업무 중 부하가 된다. cron 시간을 KST 기준 새벽으로 옮긴다
   (서버 TZ 변경은 같은 호스트의 다른 서비스에 영향을 주므로 cron 시각만 조정).
4. **매뉴얼 서버 백업이 원본과 같은 디스크에 있다.** 실서버 조사 확인(2026-09-02): 물리
   디스크가 `sda` 하나뿐이고 `/`·`/home`이 같은 btrfs subvolume이다. `/srv/qa-manual-hub/
   backup`(276M)과 `storage`(58M) 모두 `/dev/sda3` 위에 있어 디스크 장애 시 함께 소실된다.
   `/mnt/vhdmaster`가 별도 마운트로 있지만 운영 보호 규칙상 접근·마운트 변경 금지 대상이라
   쓸 수 없다. **여분 디스크가 없어 이 서버만으로는 해결 불가 — 별도 볼륨/NAS 추가라는
   인프라 결정이 먼저 필요하다** (보류, 사용자 결정 대기).
5. ~~**HTTPS 미적용.**~~ → **완료 (2026-09-02)**. self-signed 인증서(`/etc/nginx/ssl/
   qa-platform/`, CN=10.13.0.222, 825일)를 발급해 `listen 443 ssl` 추가, 포트 80은 443으로
   강제 리다이렉트, Manual Hub `.env`의 `SESSION_COOKIE_SECURE=true`로 전환.
   `scripts/monitor_health.py`(cron)가 평문 HTTP로 `/health`·`/manual-hub/api/health`를
   조회하다가 리다이렉트→self-signed 인증서 검증 실패로 깨지는 문제를 실제로 재현했고,
   `location = /health`/`location = /manual-hub/api/health`를 loopback 전용 예외로 둬서
   해결(단, `return 301`을 server 최상위에 바로 두면 location 매칭보다 rewrite phase가
   먼저 실행돼 exact-match location이 무시되는 nginx 특성이 있어 `location / { return 301
   ...; }`로 감싸야 했다 — 실제로 이 순서 문제를 겪고 고쳤다). 주요 7개 경로 https 200,
   monitor 스크립트 `{"status":"ok", ...}` 재확인, 다른 보호 서비스(5000/5001/5002/5003/
   8000/10000/18800, qa-verification PID 불변) 전부 유지 확인. `deploy/nginx/
   qa-platform.conf` 갱신, 배포 전 파일은 서버 `/etc/nginx/backups/`에 백업됨.
6. ~~**nginx의 구 주소 호환 블록은 임시 조치다.**~~ → **완료 (2026-09-02)**. 핵심 앱 라우터
   전체(`impact_analyzer`/`manual_review`/`knowledge`/`cost_dashboard`)를 grep해 호환
   블록이 가로채던 경로(`/products`, `/documents`, `/search`, `/recent`, `/users`,
   `/categories`, `/audit`, `/settings`, `/account`, `/login`, `/api/`)와 겹치는 경로가
   하나도 없음을 확인한 뒤 제거. 통합 전 주소를 직접 북마크/캐시해둔 사용자가 있다면 이제
   404를 본다(사용자 승인 후 진행).

### B. 제품 기능 고도화

7. ~~**두 시스템의 데이터가 아직 연결되지 않았다.**~~ → 완료. 실서버 활성화·검증까지 끝났다 (위 참고). 매뉴얼 개정 검증이 참조하는 매뉴얼과
   매뉴얼 서버에 보관된 매뉴얼이 서로를 모른다. 매뉴얼 서버 API로 제품의 Current 매뉴얼을
   가져와 개정 검증의 Cross-Manual 대조 대상으로 쓰면, 지금 수동으로 올리는 과정이 사라진다.
   저장소를 합친 이유를 실제 기능으로 잇는 항목이며, **이번 통합의 가장 큰 미개척 시너지**다.
   단, 하위 서비스는 코드·DB를 공유하지 않는다는 경계를 지켜 HTTP API로만 연동한다.
8. ~~**추천 정확도 측정 루프가 실제로 돌지 않는다.**~~ — **완료 (2026-09-02).** 완료된 분석
   상세 화면에서 QA 확정 TC ID와 메모를 SQLite에 적립하고, 분석별 및 누적 micro
   precision/recall/F1·누락·과추천을 즉시 표시한다. “대상 없음”도 빈 정답으로 저장할 수 있다.
   아직 QA 확정 표본은 사용자가 실제 검증을 마친 분석부터 쌓아야 하며, 9번의
   `candidate_limit` 조정은 표본이 쌓인 뒤 수행한다.
9. **`retrieval.candidate_limit=150`이 검증되지 않았다.** 실서버 표본 1건(전체 TC 6,407 →
   후보 150 → 최종 추천 3)만으로 정한 값이다. 8번이 선행되어야 조정 근거가 생긴다.
10. **Word Comment 앵커링이 문단 단위다.** 정확한 run 범위를 추적하지 않는다(의도적 v1).
11. **Release Scope BM25 매칭 오판.** functional change가 2건 이하면 관련 항목도 "누락 의심"
    으로 나올 수 있다. 현재는 참고 신호로만 취급하도록 문서화돼 있다.
12. **매뉴얼 서버 확장 항목.** 본문 full-text 검색(현재 PostgreSQL ILIKE → `tsvector`),
    변경 알림(Email/Teams), Revision 자동 추출, 권한 고도화. 구조는 준비돼 있고 미구현이다
    (`services/qa-manual-hub/README.md` "향후 확장").

### C. 구조 · 기술 부채

13. **`app/parsers/*`의 계층 역전.** `document_parser`·`excel_parser`·`pdf_parser`가
    `app.modules.impact_analyzer.schemas`를 import한다. 공용 파서가 특정 모듈에 의존하는
    구조라, 스키마를 `app/core/`로 올려야 한다.
14. **핵심 앱 스키마 마이그레이션 방식.** 현재 `CREATE TABLE IF NOT EXISTS` + 컬럼 보강이다.
    `docs/SHARED_PLATFORM_ARCHITECTURE.md`가 정한 전환 시점(운영 인스턴스나 개발자 증가)에
    도달하면 Alembic으로 옮긴다. 매뉴얼 서버는 이미 Alembic을 쓴다.
15. **핵심 앱 배포가 수동이다.** `scripts/deploy.ps1`이 파일만 복사하고 `pip install`과
    재기동은 사람이 한다. 매뉴얼 서버의 `deploy.sh`(의존성 동기화 + 마이그레이션 + 재시작 +
    헬스체크)와 비대칭이다. 1번의 systemd 유닛이 생기면 같은 수준으로 맞출 수 있다.
16. ~~**로컬 폴더 rename 미완료.**~~ → 완료 (2026-09-02 확인, `HANDOFF.md` §2 참고). 사용자가
    세션 밖에서 직접 rename하고 작업 스케줄러 경로도 갱신했다.
17. **구 GitHub 저장소 정리.** `hongmin3/qa-manual-hub`는 병합 후에도 그대로 남아 있다.
    새 저장소에서 정상 동작이 확인됐으므로 Archive 처리 시점이다.

### D. Akela 지식 운영

18. **learnings 파이프라인이 한 번도 쓰이지 않았다.** `akela stats`의 citation compliance가
    31개 run 전부 `0/N learnings`다. 섹션 인용(28/31)은 잘 되는데, 작업 중 새로 알게 된 것을
    `akela vet` → LEARNINGS.md로 올리는 경로가 비어 있다.
19. **매뉴얼 서버 지식 31개 섹션이 아직 한 번도 applied되지 않았다.** 병합하며 편입만 했고
    그 activity로 실제 작업을 한 적이 없다. 다음 매뉴얼 서버 작업 때 실제로 쓸모가 있는지
    검증해야 한다.
20. **CURATE 정기 검토가 설정되지 않았다.** `akela/CURATE.md`는 주기적 검토를 전제하는데
    아직 한 번도 돌리지 않았다. `scope=all` + `tier=should` 섹션이 30번 컴파일 내내 버려지던
    문제를 뒤늦게 발견한 것도 이 검토가 없었기 때문이다.

## 알려진 설계상 단순화 (버그 아님, 의도적 v1 범위)

- Word Comment는 항상 "변경이 속한 문단 전체"에 앵커링된다 — 정확한 run 범위는 추적 안 함.
- `match_release_changes`의 BM25 매칭은 functional_changes가 아주 적으면(2건 이하) 관련
  있는 항목도 "누락 의심"으로 오판할 수 있다 — 항상 "QA 확인 필요"라는 참고 신호로만 취급할 것.
- `app/parsers/{document_parser,excel_parser,pdf_parser}.py`가 `app.modules.impact_analyzer.schemas`를
  import하는 결합은 여전히 남아 있다(2026-09-01 리팩터링 세션 노트 참고).
