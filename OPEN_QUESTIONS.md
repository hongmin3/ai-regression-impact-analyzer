# Open Questions — 진행 전 확인이 필요한 결정

2026-09-01 세션에서 "매뉴얼 개정 검증"(`app/modules/manual_review/`) 기능을 실제로
동작하는 파이프라인까지 구현했습니다. 아래 1~3번은 "쭉 진행해달라"는 요청에 따라 이번
세션에서 직접 결정하고 구현까지 마쳤습니다 — 결과가 마음에 안 들면 언제든 바꿀 수 있으니
확인해주세요. 실제 예시 파일의 E2E 편입 결정도 완료됐습니다.

## 완료된 결정 (변경 원하시면 말씀해주세요)

1. **`manual_review` 네이밍**: `app/modules/manual_review/` + URL `/manual-review`로 확정하고 계속 사용했습니다.
2. **`manual_revisions`/`manual_changes`/`manual_comments` 스키마**: 다음과 같이 확정해 실제로 사용 중입니다.
   - `manual_revisions`: `round_number`/`parent_revision_id`/`baseline_revision_id`로 Round 계보 추적 (Round N의 baseline은 항상 최초 Round 0을 가리킴)
   - `manual_changes`: `functional`(NON_FUNCTIONAL_CHANGE 필터 결과) + `decision`/`confidence`/`ai_judgment_json`(AI 판정) + `qa_decision`/`qa_note`(QA Override, AI 원본은 보존)
   - `manual_comments`: `status`(OPEN/RESOLVED/NOT_RESOLVED/REOPENED/IGNORED_BY_QA) + `resolved_in_revision_id`
   - Round N+1 검증 시 전체 이전 Round의 OPEN/NOT_RESOLVED/REOPENED Comment를 이어받고,
     현재 Track Changes와 로컬 유사도를 비교해 `반영 의심/미반영 의심/판단 불가`를 참고
     표시합니다. 자동으로 해결 상태를 확정하지 않으며 QA가 직접 최종 상태를 선택합니다.
   - Cross-Manual 영향분석 저장 위치는 아직 미착수(SRS/Release Note/Design Review 파서가 없어 스코프 자체가 없음).
3. **`python-docx` 의존성**: 추가했습니다(`requirements.txt`, 실제 설치된 버전 `1.2.0`). Word Comment 삽입(`app/modules/manual_review/comment_writer.py`)에 사용 중이며, `Document.add_comment()` + 직접 lxml로 `<w:ins>/<w:del>` 내부 run을 찾아 앵커링하는 방식으로 구현했습니다(python-docx의 `Paragraph.runs`는 이런 wrapper 내부 run을 못 찾아서 우회 필요).

## E2E 테스트용 실제 예시 파일 — 완료 (2026-09-01, 고정 경로 참조 + skip 방식으로 편입)

**결정**: 실제 파일을 리포지토리 밖 고정 경로에 두고 테스트에서 그 경로를 참조하되(옵션 1),
경로 자체(사내망 서버 IP·부서 폴더 체계)도 `.deploy.env`와 동일하게 Git 제외 대상인
`real_fixtures.local.env`로 분리했다(공개 GitHub repo에 사내 폴더 구조를 노출하지 않기
위함, 사용자 확인 완료). 값 없는 예제는 `real_fixtures.local.env.example`로 공개.

**구현**: `tests/test_manual_review_real_files_e2e.py`. `real_fixtures.local.env`가 없거나
경로에 접근할 수 없는 환경(GitHub Actions 등)에서는 `pytest.mark.skipif`로 자동 skip.
이 PC에서는 실제 VXvue 1.1.0 Round 1 Service Manual(.docx, Track Changes 799건)·Release
Note(67건)·설계검토보고서(40건)·SRS 사양서 6개로 `ManualRevisionReviewer.run()` 전체를
mock AI로 실행해 통과 확인(약 70초 소요 — `pytest -q` 전체 실행 시간에 그대로 반영됨을
인지할 것).

이 파일들은 여전히 **리포지토리에 커밋하지 않는다** — 테스트는 사용자 PC의 로컬/사내망
경로만 참조한다. 다른 팀원 PC나 CI 환경에서는 `real_fixtures.local.env.example`을 복사해
값을 채우지 않는 한 이 테스트가 자동으로 skip되며, 이는 의도된 동작이다.
