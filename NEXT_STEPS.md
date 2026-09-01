# Next Steps — 매뉴얼 개정 검증 기능 진행 상황 (우선순위 순)

> **2026-09-01 사용자 결정: 아래 두 항목은 보류(우선순위 낮음, 삭제 아님)**
> - 로컬 폴더 rename(대상 이름 `qa-verification-management-system`, `HANDOFF.md` §2에
>   정확한 명령 있음, 이 세션이 폴더를 물고 있어 세션 내부에서는 구조적으로 불가능함을
>   2026-09-01 재확인). 필요해지면 `HANDOFF.md` §2 명령으로 재개.
> - Release Note/설계검토보고서 주간 자동 확보(`OPEN_QUESTIONS.md` #4) — 현재 수동
>   업로드+자동 재사용으로 충분하다고 판단해 보류.

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
- 아직 커밋/push/배포는 하지 않음.

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

## 아직 미착수 (우선순위 순)

1. ~~**Cross-Manual 영향분석**~~ (스펙 §11) → 완료(위 7차 세션 참고).
2. ~~**이미지 변경 Human Review Gate**~~ (스펙 §8-1) → 완료(위 7차 세션 참고).
3. ~~**비용/캐시 대시보드 UI**~~ → 완료(위 참고). 매뉴얼 개정 검증의 캐시 Hit 기록은 아직
   없음(위 "알려진 v1 범위" 참고) — 필요 시 `manual_review/ai_client.py`에도
   `ai_audit`/`cache_hit` 기록 추가 검토.
4. ~~**실제 예시 파일 기반 E2E pytest 테스트 추가**~~ → 완료. `tests/test_manual_review_real_files_e2e.py`,
   경로는 Git 제외 대상 `real_fixtures.local.env`(`.example` 참고)에서 읽는다. 상세는
   `OPEN_QUESTIONS.md` #5 참고. **주의**: 이 PC(`real_fixtures.local.env` 설정됨)에서는
   `pytest -q` 전체 실행 시간이 약 10초 → 약 80초로 늘어난다(대용량 실제 PDF/DOCX 파싱 +
   BM25 후보 검색을 779건 functional change에 대해 반복 수행하기 때문). 경로가 없는 다른
   환경(원격 서버, CI)에서는 즉시 skip되어 영향 없음.
## 알려진 설계상 단순화 (버그 아님, 의도적 v1 범위)

- Word Comment는 항상 "변경이 속한 문단 전체"에 앵커링된다 — 정확한 run 범위는 추적 안 함.
- `match_release_changes`의 BM25 매칭은 functional_changes가 아주 적으면(2건 이하) 관련
  있는 항목도 "누락 의심"으로 오판할 수 있다 — 항상 "QA 확인 필요"라는 참고 신호로만 취급할 것.
- `app/parsers/{document_parser,excel_parser,pdf_parser}.py`가 `app.modules.impact_analyzer.schemas`를
  import하는 결합은 여전히 남아 있다(2026-09-01 리팩터링 세션 노트 참고).
