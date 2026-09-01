# Next Steps — 매뉴얼 개정 검증 기능 진행 상황 (우선순위 순)

## 2026-09-01 Cross-Manual/이미지 Gate 마무리 + 명칭 통일 (완료)

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
- **명칭 통일**: 표시명 **QA 검증 관리 시스템**, GitHub repo/로컬 폴더 slug
  **qa-verification-management-system**(상세는 `HANDOFF.md` §2). 원격 Ubuntu 배포 경로는
  운영 중인 서비스라 의도적으로 이전 이름 유지.

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

1. **Cross-Manual 영향분석** (스펙 §11) — 구현 완료, 테스트/문서/커밋 마무리 필요.
2. **이미지 변경 Human Review Gate** (스펙 §8-1) — 구현 중, 합성 PDF 이미지 테스트 1건 수정 필요.
3. **비용/캐시 대시보드 UI** — 토큰 사용량은 이미 기록되지만 화면 노출 UI는 없음.
4. **실제 예시 파일 기반 E2E pytest 테스트 추가** — 이번 세션에서 수동으로 스크립트를 돌려
   검증은 했지만(실제 회사 문서라 테스트 fixture로 커밋하지 않음), 이 실제 파일들을 pytest
   fixture로 안전하게 참조할 방법(예: 사내망 접근 가능한 CI에서만 skip 없이 실행)을 정하면
   정식 E2E 테스트로 승격 가능.
## 알려진 설계상 단순화 (버그 아님, 의도적 v1 범위)

- Word Comment는 항상 "변경이 속한 문단 전체"에 앵커링된다 — 정확한 run 범위는 추적 안 함.
- `match_release_changes`의 BM25 매칭은 functional_changes가 아주 적으면(2건 이하) 관련
  있는 항목도 "누락 의심"으로 오판할 수 있다 — 항상 "QA 확인 필요"라는 참고 신호로만 취급할 것.
- `app/parsers/{document_parser,excel_parser,pdf_parser}.py`가 `app.modules.impact_analyzer.schemas`를
  import하는 결합은 여전히 남아 있다(2026-09-01 리팩터링 세션 노트 참고).
