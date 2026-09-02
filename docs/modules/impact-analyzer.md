# Regression 영향 분석 (`/impact-analyzer`)

> 코드: [`app/modules/impact_analyzer/`](../../app/modules/impact_analyzer)
> · 앱 안 사용법: `/impact-analyzer/guide`
> · 상위 문서: [README](../../README.md) · [문서 지도](../README.md)

SW 변경사항을 등록된 제품 사양서·Test Case와 대조해, 이번 변경으로 **다시 검증해야 하는
TC**와 그 판단 근거를 추천한다.

## 무엇을 해결하는가

SW 변경이 생겼을 때 "이번엔 어디까지 다시 봐야 하는가"는 대부분 담당자의 경험에 의존한다.
사람이 판단하면 이런 문제가 생긴다.

- 담당자에 따라 검증 범위가 달라진다 (재현되지 않는 기준)
- 사양서가 여러 리비전으로 쌓이면 "무엇이 실제로 바뀌었는지"부터 다시 찾아야 한다
- TC가 수백 건이면 관련 TC를 눈으로 훑는 데만 시간이 든다
- 빠뜨린 TC가 있어도 사후에 그 사실을 확인할 방법이 없다

## 처리 흐름

```text
변경 문서 (여러 개 첨부 가능 / 문서 없이 요청 텍스트만도 가능)
  ↓ 기준 사양서와 diff — "진짜 바뀐 줄"만 남긴다
Change 추출 (Rule 기반, 결정적)
  ↓ BM25 검색 — 사양서 근거 상위 K건
Specification 근거 선정
  ↓ Rule 기반 후보 압축 — TC 후보 N건까지
TC Candidate 선정
  ↓ Gemini Structured Output — 분석 1건당 정확히 1회 호출
의미적 판정 (검증 필요 / 불필요 + 근거 + Confidence)
  ↓ TC ID · Chunk ID 교차검증 — 모델이 지어낸 ID를 걸러낸다
HTML 보고서 + XLSX + 신규 TC 초안(md)
```

각 단계에서 LLM에 실제로 도달하는 입력을 어떻게 줄이는지는
[비용 절감 설계](../COST_OPTIMIZATION.md)에 단계별로 정리했다.

## 설계상 중요한 결정

**기준 사양서 diff를 먼저 한다.** 변경 문서 전체에서 키워드를 뽑으면, 바뀌지 않은 문장까지
변경으로 오인해 불필요한 AI 판정을 만든다. 등록된 기준 사양서와 실제로 diff해서 바뀐 줄만
분석 대상으로 삼는다 (`regression_analyzer.py`).

**모델이 만든 ID를 그대로 믿지 않는다.** 응답의 TC ID와 근거 Chunk ID가 실제 데이터에
존재하는지 교차검증한다. 존재하지 않으면 결과에서 제외된다 (`validation.py`).

**Confidence로 사람의 개입 지점을 나눈다.** `analysis.recommended_confidence`(기본 0.80)
이상은 추천, `review_confidence`(기본 0.60) 이상은 Manual Review 대상으로 분류한다. 낮은
확신을 조용히 추천으로 올리지 않는다.

**커버되지 않는 변경은 신규 TC 초안으로 남긴다.** 기존 TC 어느 것으로도 검증되지 않는
변경이 발견되면 "해당 없음"으로 끝내지 않고 신규 TC 초안(md)을 생성한다.

**진행 상태는 실제 백엔드 단계다.** SSE로 현재 단계를 그대로 흘려보낸다. 시간이 지나면
올라가는 가짜 퍼센트를 쓰지 않는다.

## 결과물

| 산출물 | 내용 |
|---|---|
| HTML 보고서 | 의미 단위 Change Summary, 단순화된 TC 표, 사람이 읽는 사양 근거 |
| XLSX | 추천 TC 목록 (검증 계획에 그대로 붙여 쓸 수 있는 형태) |
| 신규 TC 초안 (md) | 기존 TC로 커버되지 않는 변경에 대한 초안 |
| 분석 상세 화면 | 요청 문서, Knowledge 근거, System Instruction, Gemini에 실제로 전달된 입력 JSON과 원본 응답, 모델·캐시·생성 설정, BM25 후보 순위와 점수 |

마지막 항목이 이 기능의 감사 근거다. "AI가 왜 이렇게 판단했는가"를 사후에 그대로 열어볼 수
있어야 검증 결과를 업무에 쓸 수 있다.

## 관련 설정 (`config.yaml`)

| 키 | 기본값 | 의미 |
|---|---|---|
| `retrieval.specification_top_k` | 8 | LLM에 넣을 사양서 근거 개수 |
| `retrieval.candidate_limit` | 150 | TC 후보 상한 |
| `retrieval.change_text_top_lines` | 60 | 요청 관련 변경 문서 줄 수 상한 |
| `analysis.recommended_confidence` | 0.80 | 추천 분류 기준 |
| `analysis.review_confidence` | 0.60 | Manual Review 분류 기준 |
| `analysis.cache_enabled` | true | 동일 입력 응답 캐시 |
| `analysis.daily_token_limit` | 0 (비활성) | 일일 토큰 한도 |
| `analysis.max_concurrent_jobs` | 2 | 동시 분석 실행 수 |

## 정확도 평가

QA가 확정한 정답과 분석 결과를 비교해 precision·recall·F1과 누락/과추천 TC를 계산하는 절차는
[정확도 평가](../EVALUATION.md)에 있다.
