# 매뉴얼 개정 검증 (`/manual-review`)

> 코드: [`app/modules/manual_review/`](../../app/modules/manual_review)
> · 앱 안 사용법: `/manual-review/guide`
> · 상위 문서: [README](../../README.md) · [문서 지도](../README.md)

연구소가 제출한 Word Track Changes(`.docx`) 개정 Manual이 최신 SRS(= Regression 영향 분석이
이미 동기화하고 있는 등록 사양서)를 정확히 반영했는지 AI로 1차 검토한다.

## 처리 흐름

```text
개정 Manual (.docx Track Changes / .pdf)
  ↓ 구조화 추출 — 삽입·삭제·서식 변경을 항목 단위로 분해
Track Changes 추출
  ↓ Rule 필터 — 페이지 번호, 저작권 표기, 목차 리더 점선 등은 AI 대상에서 제외
NON_FUNCTIONAL_CHANGE 제거
  ↓ 로컬 BM25 — 이 변경과 관련된 SRS 근거만
SRS 근거 검색
  ↓ Release Note · 설계검토보고서 Scope 대조
범위 대조
  ↓ 같은 제품의 다른 매뉴얼과 BM25 대조
Cross-Manual 영향 추적
  ↓ quick 판정 → PASS면 종료, 의심되면 detail 판정
2단계 AI 판정
  ↓ QA Override 가능
결과 화면 → Word Comment 삽입 DOCX 다운로드
```

## 사람이 반드시 확인하게 만드는 지점

이 기능의 핵심 설계는 "AI가 판단할 수 없는 것을 AI가 판단하지 않게 하는 것"이다.

**이미지 변경 Human Review Gate.** DOCX Track Changes 안의 삽입·삭제된 drawing·pict와 PDF
페이지 이미지의 SHA-256 hash 변화를 감지하면 `IMAGE_CHANGE_REVIEW_REQUIRED`로 강제
표시한다. 이미지 변경은 텍스트만으로 의미를 판단할 수 없으므로, AI가 임의로 PASS 처리하지
않고 항상 사람이 원본 이미지를 직접 확인한다.

**PDF diff는 confidence 상한을 둔다.** 첫 PDF를 Baseline으로 등록하고 다음 PDF부터 이전
PDF와 페이지별 텍스트 추가·삭제·수정을 비교한다. 위치·레이아웃 해석 오차를 감안해
confidence를 최대 60%로 제한하고 `PDF_DIFF_REVIEW_REQUIRED`를 표시하며, PDF에는 Word
Comment를 생성하지 않고 QA가 결과 화면에서 최종 판정한다.

**Cross-Manual 영향은 후보로만 표시한다.** 같은 제품의 다른 매뉴얼 최신 리비전(없으면 등록된
Knowledge 문서)을 이번 Release·설계 변경과 BM25로 대조해 관련 있어 보이는 항목을
`REVIEW_REQUIRED` 후보로 표시한다. 자동 확정하지 않고, QA가 결과 화면에서 확인 필요 / 영향
있음 / 영향 없음으로 직접 확정한다 (`cross_manual.py`).

**이전 Round 지적사항의 상태는 자동으로 바꾸지 않는다.** Round 계보를 추적하며 이전
지적사항에 대해 로컬 유사도 기반 참고 판정을 제공하지만, QA가 해결 / 미해결 / 재오픈 / 제외를
확정하기 전에는 상태를 변경하지 않는다.

## 비용 관점의 설계

- Rule Engine이 `NON_FUNCTIONAL_CHANGE`를 먼저 걷어내므로 AI 호출 대상 자체가 줄어든다
  (`change_filter.py::is_functional_change`).
- quick 판정이 PASS면 비용이 큰 detail 호출을 생략한다 (PASS short-circuit).
- 근거 SRS 후보는 `manual_review.max_srs_candidates`(기본 6)건으로 제한한다.

자세한 내용은 [비용 절감 설계](../COST_OPTIMIZATION.md).

## 결과물

| 산출물 | 내용 |
|---|---|
| 결과 화면 | 항목별 판정·근거·Confidence, QA Override |
| Word Comment 삽입 DOCX | 판정 결과를 원본 문서에 코멘트로 삽입해 연구소에 회신 |
| Round 이력 | 이전 Round 지적사항과 현재 Round의 계보 |

## 관련 설정 (`config.yaml`)

| 키 | 기본값 | 의미 |
|---|---|---|
| `manual_review.max_srs_candidates` | 6 | 근거 SRS 후보 개수 상한 |
| `storage.manual_revision_dir` | `data/manual_revisions` | 개정 Manual 원본 보관 |
| `storage.manual_review_comment_dir` | `output/manual_review_comments` | Comment 삽입 DOCX 산출 |

프롬프트는 `app/prompts/manual_revision_quick.yaml`, `manual_revision_detail.yaml` 에 버전과
함께 들어 있다.
