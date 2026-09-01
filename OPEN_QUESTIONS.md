# Open Questions — 진행 전 확인이 필요한 결정

2026-09-01 세션에서 "매뉴얼 개정 검증"(`app/modules/manual_review/`) 기능을 실제로
동작하는 파이프라인까지 구현했습니다. 아래 1~3번은 "쭉 진행해달라"는 요청에 따라 이번
세션에서 직접 결정하고 구현까지 마쳤습니다 — 결과가 마음에 안 들면 언제든 바꿀 수 있으니
확인해주세요. 4~5번은 여전히 사용자만 답할 수 있는 외부 정보/자격증명 관련 항목입니다.

## 완료된 결정 (변경 원하시면 말씀해주세요)

1. **`manual_review` 네이밍**: `app/modules/manual_review/` + URL `/manual-review`로 확정하고 계속 사용했습니다.
2. **`manual_revisions`/`manual_changes`/`manual_comments` 스키마**: 다음과 같이 확정해 실제로 사용 중입니다.
   - `manual_revisions`: `round_number`/`parent_revision_id`/`baseline_revision_id`로 Round 계보 추적 (Round N의 baseline은 항상 최초 Round 0을 가리킴)
   - `manual_changes`: `functional`(NON_FUNCTIONAL_CHANGE 필터 결과) + `decision`/`confidence`/`ai_judgment_json`(AI 판정) + `qa_decision`/`qa_note`(QA Override, AI 원본은 보존)
   - `manual_comments`: `status`(OPEN/RESOLVED/NOT_RESOLVED/REOPENED/IGNORED_BY_QA) + `resolved_in_revision_id`
   - Round N+1 검증 시 Round N의 OPEN 상태 Comment를 "이전 지적사항"으로 화면에 보여주지만, **자동으로 반영 여부를 판정하지는 않습니다** (오탐 위험이 커서 QA가 직접 확인하도록 설계 — NEXT_STEPS.md 참고).
   - Cross-Manual 영향분석 저장 위치는 아직 미착수(SRS/Release Note/Design Review 파서가 없어 스코프 자체가 없음).
3. **`python-docx` 의존성**: 추가했습니다(`requirements.txt`, 실제 설치된 버전 `1.2.0`). Word Comment 삽입(`app/modules/manual_review/comment_writer.py`)에 사용 중이며, `Document.add_comment()` + 직접 lxml로 `<w:ins>/<w:del>` 내부 run을 찾아 앵커링하는 방식으로 구현했습니다(python-docx의 `Paragraph.runs`는 이런 wrapper 내부 run을 못 찾아서 우회 필요).

## 아직 열려 있는 질문

### 4. ALM 크롤러 서브프로세스를 이 기능에도 재사용할지 — 부분 해결

**SRS**: 이미 impact_analyzer가 관리하는 `documents(kind='specification')` 테이블(=
`vxvue_spec_sync.py`가 매주 자동 최신화하는 바로 그 SRS)을 그대로 재사용하도록 구현했습니다
(`app/modules/manual_review/srs_evidence.py`). 별도 크롤러 연동이 필요 없습니다.

**Release Note/설계검토보고서**: 자격증명이 걸린 새 자동화는 만들지 않고, 대신 **수동 업로드 +
자동 재사용** 방식으로 구현했습니다 — 검증 등록 화면에서 파일을 첨부하면 `documents` 테이블에
`release_note`/`design_review` kind로 등록되고, 다음 검증부터는 파일을 다시 첨부하지 않아도
해당 제품에 등록된 가장 최근 문서를 자동으로 사용합니다(`router.py::_register_or_reuse_reference_doc`).
매주 자동 확보(Windows 작업 스케줄러 연동)까지는 아직 하지 않았습니다 — 필요하시면 말씀해주세요.

### 5. E2E 테스트용 실제 예시 파일 — 위치 확보 완료, pytest 편입은 미결정

사용자가 사내 문서 저장소의 실제 파일 위치를 제공해주셔서(대화 중 공유, 이 문서에는 경로를
남기지 않음) VXvue 1.1.0의 실제 Round 1 매뉴얼(Track Changes 포함)·Release Note·설계검토
보고서·등록 사양서(SRS)로 파이프라인 전체(`ManualRevisionReviewer.run()`)를 실제로 실행해
검증했습니다.

이 검증 과정에서 `release_scope.py`의 실제 버그 여러 건을 발견해 수정했습니다(자세한 내용은
`NEXT_STEPS.md`). 다만 이 파일들은 **사내 기밀 문서라 리포지토리에 커밋하거나 pytest fixture로
포함하지 않았습니다** — 이번 검증은 임시 스크립트로 수동 실행 후 삭제하는 방식으로 진행했습니다.

남은 질문: 이 실제 파일들을 정식 pytest E2E 테스트로 편입하고 싶으신가요? 편입한다면
1) 파일을 리포지토리 밖 고정 경로에 두고 테스트에서 그 경로를 참조(경로가 없는 환경에서는
skip), 2) 아예 별도의 비공개 테스트 저장소를 두는 방법 중 어느 쪽을 원하시는지 확인이
필요합니다. 결정 전까지는 지금처럼 합성(sanitized) fixture 기반 유닛 테스트만 pytest에 남깁니다.
