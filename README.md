# QA 검증 관리 시스템

SW 변경사항과 제품 사양서·Test Case·매뉴얼을 결합해 Regression 검증 대상과 매뉴얼 개정
누락을 자동으로 찾아주는 QA 업무자동화 서비스입니다. 사용자는 브라우저에서 제품을 고르고
관련 문서를 올리기만 하면 되고, 별도의 AI 채팅이나 Prompt 작성이 필요 없습니다.

## 왜 비용 절감이 핵심 설계 원칙인가

사양서·TC·매뉴얼 원문을 통째로 LLM에 넘기면 정확도는 높아 보여도 호출당 토큰이 급증하고,
분석 1건마다 비용이 선형으로 늘어나 사내 서비스로 지속 운영하기 어렵습니다. 이 프로젝트는
**"판단이 꼭 필요한 지점에서만, 최소한의 근거로 LLM을 부른다"**를 원칙으로 삼아, 파싱·검색·
후보 압축·1차 필터링은 전부 결정적인 Python Rule Engine이 처리하고 Gemini는 의미적 판단이
꼭 필요한 마지막 단계에서 구조화된 입력으로 단 한 번(또는 조건부로 그 이하) 호출됩니다.

## 비용 절감 파이프라인

실제 호출까지 도달하는 입력을 단계마다 줄이는 구조입니다. 괄호 안은 관련 코드/설정입니다.

1. **Rule Engine 사전 필터** — 매뉴얼 검증에서 페이지 번호·저작권 표기·목차 리더 점선 같은
   `NON_FUNCTIONAL_CHANGE`는 애초에 AI 분석 대상에서 제외합니다
   (`app/modules/manual_review/change_filter.py::is_functional_change`).
2. **기준 사양서 Diff** — 변경 문서 전체에서 키워드를 뽑는 대신 등록된 기준 사양서와 실제
   diff해 "진짜 변경된 줄"만 분석 대상으로 삼습니다. 미변경 문장을 변경으로 오인해 불필요한
   AI 판정을 만드는 문제를 근본적으로 막습니다 (`app/modules/impact_analyzer/regression_analyzer.py`).
3. **BM25/RAG Top-K 후보 압축** — 사양서 근거는 BM25로 상위 `retrieval.specification_top_k`
   (기본 8)건만, TC 후보는 `retrieval.candidate_limit`(기본 150)건까지만 골라 LLM 입력에
   포함합니다. 전체 사양서·전체 TC를 매번 통째로 보내지 않습니다.
4. **변경문서 관련 줄 축소** — 사용자 요청 사항이 있으면 변경 문서 전체 대신 요청과 관련성
   높은 줄만 BM25로 추려 보냅니다(`retrieval.change_text_top_lines`, 기본 60줄). 문서가 이보다
   짧으면 그대로 전체를 사용합니다(`app/modules/impact_analyzer/change_analyzer.py::trim_by_relevance`).
5. **Structured Output 단일 호출** — Gemini는 JSON Schema로 강제된 Structured Output을
   반환하며, Regression 분석 1건당 정확히 1회만 호출합니다. 재파싱·재질의 왕복이 없습니다.
6. **매뉴얼 quick/detail 2단계 + PASS short-circuit** — 매뉴얼 개정 변경은 먼저 짧은 quick
   판정만 수행하고, 결과가 PASS면 비용이 큰 detail 호출을 생략합니다. 문제가 의심될 때만 상세
   근거·판정을 추가로 요청합니다(`app/prompts/manual_revision_{quick,detail}.yaml`).
7. **SHA-256 응답 캐시** — 모든 Gemini 호출은 `sha256(model+prompt명+prompt버전+prompt내용)`을
   키로 캐시됩니다. 동일 입력으로 재분석·재검증하면 API 호출 없이 캐시 응답을 그대로
   재사용합니다(`app/core/gemini_client.py`, `analysis.cache_enabled`).
8. **thinking_budget=0** — 이 서비스의 모든 AI 호출은 근거 기반 구조화 추출·판정이라 별도의
   내부 추론이 필요 없습니다. `thinking_config.thinking_budget=0`으로 내부 reasoning 토큰
   소비를 비활성화해 같은 `max_output_tokens` 예산을 응답 생성에 온전히 씁니다
   (`app/prompts/*.yaml`).
9. **일일 토큰 한도 + 감사 기록** — `analysis.daily_token_limit`을 넘으면 새 분석 실행 자체를
   차단합니다(`/config/status`에서 사용량 확인). 완료된 모든 호출은 요청 문서, Knowledge 근거,
   System Instruction, Gemini에 실제로 전달된 입력 JSON과 원본 응답, 모델/캐시/생성 설정,
   BM25 후보 순위·점수를 분석 상세 화면에서 그대로 열람할 수 있어 비용과 판단 근거를 사후
   검증할 수 있습니다.

## Architecture

루트(`/`)는 QA 자동화 기능을 선택하는 허브입니다. Regression 영향 분석은
`/impact-analyzer`, 매뉴얼 개정 검증은 `/manual-review`에서 시작합니다. 새 QA 기능과
공유 DB 확장 원칙은 [공용 플랫폼 아키텍처](docs/SHARED_PLATFORM_ARCHITECTURE.md)를 따릅니다.

```text
Change Document → Rule 기반 Change 추출(기준 사양서 diff) → BM25 Specification 검색
     → TC Candidate 선정 → Gemini Semantic Decision(Structured Output, 1회 호출)
     → TC ID / Chunk ID 교차검증 → HTML Report + XLSX + 신규 TC 초안(md)
```

### 코드 구조

하나의 FastAPI 서버(`app/main.py`) 안에서 여러 기능을 독립적인 URL로 서비스합니다.

```text
app/
├─ core/       공용 인프라 (설정, 저장소, Gemini 클라이언트, 프롬프트 로더, 스케줄러)
├─ prompts/    AI 프롬프트 YAML (버전 관리, thinking_budget 등 생성 설정 포함)
├─ modules/
│   ├─ impact_analyzer/   Regression 영향도 분석 기능 (URL: /impact-analyzer, /analyses ...)
│   ├─ manual_review/     매뉴얼 개정 검증 기능 (URL: /manual-review)
│   └─ knowledge/         두 기능이 공유하는 사양서·TC 관리 (URL: /knowledge)
└─ web/        모듈별 라우터를 한 서버에 취합하는 얇은 공용 계층 + 공용 template/static
```

각 모듈은 자신의 라우터·스키마·서비스 로직·템플릿을 소유하며, `app/web/router.py`가 URL prefix만 결정해 하나의 서버에 붙입니다.

## 매뉴얼 개정 검증 (`/manual-review`)

연구소가 제출한 Word Track Changes(`.docx`) 개정 Manual이 최신 SRS(=impact_analyzer가 이미
동기화하는 등록 사양서)를 정확히 반영했는지 AI로 1차 검토합니다.

- Track Changes 구조화 추출 → NON_FUNCTIONAL_CHANGE 필터링 → SRS 근거 로컬 BM25 검색 →
  Release Note/설계검토보고서 Scope 대조 → **다른 Manual 영향 추적(Cross-Manual)** →
  quick/detail 2단계 AI 판정 → 결과 화면(QA Override 가능) → Word Comment 삽입 DOCX 다운로드.
- **Cross-Manual 영향분석**: 같은 제품의 다른 매뉴얼 최신 리비전(없으면 등록된 Knowledge
  문서)을 이번 Release/설계 변경과 BM25로 대조해, 관련 있어 보이는 다른 매뉴얼 항목을
  `REVIEW_REQUIRED` 후보로 표시합니다. 자동 확정이 아니라 QA가 결과 화면에서 확인
  필요/영향 있음/영향 없음으로 직접 확정합니다(`app/modules/manual_review/cross_manual.py`).
- **이미지 변경 Human Review Gate**: DOCX Track Changes 내부의 삽입/삭제된 drawing·pict와
  PDF 페이지 이미지의 SHA-256 hash 변화를 감지해 `IMAGE_CHANGE_REVIEW_REQUIRED`로 강제
  표시합니다. 이미지 변경은 텍스트만으로 의미를 판단할 수 없으므로 AI가 임의로 PASS 처리하지
  않고 항상 사람이 원본 이미지를 직접 확인하도록 합니다.
- **PDF 매뉴얼 diff**: 첫 PDF를 Baseline으로 등록하고 다음 PDF부터 이전 PDF와 페이지별 텍스트
  추가·삭제·수정을 비교합니다. 위치/레이아웃 해석 오차를 감안해 confidence를 최대 60%로
  제한하고 `PDF_DIFF_REVIEW_REQUIRED`를 표시하며, PDF에는 Word Comment를 생성하지 않고 QA가
  결과 화면에서 직접 최종 판정합니다.
- Round 계보를 추적하며 이전 지적사항은 로컬 유사도 기반 참고 판정을 제공하고, QA가
  해결/미해결/재오픈/제외를 확정하기 전에는 상태를 자동 변경하지 않습니다.

남은 작업은 [`NEXT_STEPS.md`](NEXT_STEPS.md), 결정이 필요한 항목은
[`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md)를 참고하세요.

## 주요 기능

- PDF/Word(`.docx`) 사양서, 다중 시트 TC Excel 자동 파싱
- 제품만 선택하면 등록된 사양서·TC 전체를 자동 검색하는 분석 워크플로, 변경 문서는 여러 개
  동시 첨부 가능, 문서 없이 요청 텍스트만으로도 분석 가능
- 실제 백엔드 단계 기반 실시간 진행 상태(SSE) — 가짜 퍼센트 없음
- 사용자 관점으로 재구성한 HTML 보고서(의미 단위 Change Summary, 단순화된 TC 표, 사람이
  읽는 사양 근거)와 분석 상세 감사 화면(요청/근거/System Instruction/Gemini 실제 입출력 JSON)
- TC ID·Chunk ID 교차검증, Confidence 기반 Manual Review 분류
- 기존 TC로 커버되지 않는 변경에 대한 신규 TC 초안 자동 생성
- VXvue 최신 사양서를 별도 자동화(Polarion 연동)와 연계해 매주 월요일 Windows 작업
  스케줄러로 자동 확보, 이전 리비전 자동 정리 (`docs/AUTOMATION.md`)
- 제품/버전별 지식 문서 관리(등록·삭제), 분석 이력·Impact 집계 대시보드

## Tech Stack

FastAPI · Jinja2 · SQLite · PyMuPDF · openpyxl · rank-bm25 · Google Gemini (Structured Output) · pytest

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item secrets.example.txt secrets.txt -Force   # GEMINI_API_KEY 입력
.\scripts\run.ps1                                   # http://localhost:12000
```

앱 실행 후 회귀 분석은 `/impact-analyzer/guide`, 매뉴얼 개정 검증은
`/manual-review/guide`에서 각각 전용 사용법을 확인할 수 있습니다. 기존 `/guide` 주소는
회귀 분석 사용법으로 연결됩니다. 서버에 직접 배포하는 상세 절차는
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)를 참고하세요.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Unit Test는 Gemini Mock Response를 사용하므로 API 비용이 발생하지 않습니다.
