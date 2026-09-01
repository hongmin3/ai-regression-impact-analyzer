# Next Steps — 매뉴얼 개정 검증 기능 진행 상황 (우선순위 순)

## 2026-09-01 세션에서 완료

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

1. **이전 Round 미해결 Comment 자동 반영 판정** — 여전히 화면 참고 표시만 하고 자동 판정은
   하지 않음(오탐 위험). 이번 세션에서 확인한 BM25의 "말뭉치가 작으면 관련 있어도 점수가
   0이 되는" 특성(`release_scope.py::match_release_changes` docstring 참고)을 감안하면,
   자동 판정을 붙이더라도 반드시 신뢰도 낮은 "참고용"으로 설계해야 한다.
2. **PDF 매뉴얼 리비전 diff** (스펙 §9) — 지금은 DOCX Track Changes만 지원.
3. **Release Note "Description for Each Version" 절의 상세 설명 활용** — 지금은 이 절을
   중복 방지를 위해 건너뛰지만, Before/Now 형식의 상세 설명은 AI 판정 시 추가 근거로 쓸 수
   있다. 파싱이 더 복잡해(표 형태 아님, 산문형 Before/Now 쌍) 이번 세션에서는 보류.
4. **설계검토보고서 "변경 결과" 표 자체 활용** — PyMuPDF가 표를 컬럼 구분 없이 풀어버려 이번
   세션에서는 "문제 분석" 절의 제목으로 대체했다(실제 검증 결과 제목이 동일해 대체 가능).
   "결과: Pass/Fail" 컬럼까지 활용하면(예: Fail 항목만 별도 강조) 더 정교해질 수 있음.
5. **Cross-Manual 영향분석** (스펙 §11) — 한 SRS/Release 변경이 여러 Manual에 영향을 주는지
   추적. 지금 Reverse 검증은 "이 Manual 안에서" 만 확인하고 다른 Manual은 보지 않는다.
6. **이미지 변경 Human Review Gate** (스펙 §8-1) — 아직 미착수. 실제 이미지 포함 매뉴얼
   예시로 검증 필요.
7. **비용/캐시 대시보드 UI** — 토큰 사용량은 이미 기록되지만 화면 노출 UI는 없음.
8. **실제 예시 파일 기반 E2E pytest 테스트 추가** — 이번 세션에서 수동으로 스크립트를 돌려
   검증은 했지만(실제 회사 문서라 테스트 fixture로 커밋하지 않음), 이 실제 파일들을 pytest
   fixture로 안전하게 참조할 방법(예: 사내망 접근 가능한 CI에서만 skip 없이 실행)을 정하면
   정식 E2E 테스트로 승격 가능.
9. **원격 서버 배포** — 이번 세션 변경분이 아직 원격 서버에 반영되지 않음. `requirements.txt`에
   `python-docx` 추가됐으므로 배포 시 서버에서 `pip install -r requirements.txt` 재실행 필요.

## 알려진 설계상 단순화 (버그 아님, 의도적 v1 범위)

- Word Comment는 항상 "변경이 속한 문단 전체"에 앵커링된다 — 정확한 run 범위는 추적 안 함.
- `match_release_changes`의 BM25 매칭은 functional_changes가 아주 적으면(2건 이하) 관련
  있는 항목도 "누락 의심"으로 오판할 수 있다 — 항상 "QA 확인 필요"라는 참고 신호로만 취급할 것.
- `app/parsers/{document_parser,excel_parser,pdf_parser}.py`가 `app.modules.impact_analyzer.schemas`를
  import하는 결합은 여전히 남아 있다(2026-09-01 리팩터링 세션 노트 참고).
