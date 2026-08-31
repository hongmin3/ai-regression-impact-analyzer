# AI Regression Impact Analyzer

SW 변경사항과 제품 사양서·Test Case를 결합해 Regression 검증이 필요한 TC를 자동 추천하는 QA 업무자동화 서비스입니다. 사용자는 브라우저에서 제품을 고르고 변경 관련 문서를 올리기만 하면 되고, 별도의 AI 채팅이나 Prompt 작성이 필요 없습니다.

## Architecture

```text
Change Document → Rule 기반 Change 추출(기준 사양서 diff) → BM25 Specification 검색
     → TC Candidate 선정 → Gemini Semantic Decision(Structured Output)
     → TC ID / Chunk ID 교차검증 → HTML Report + XLSX + 신규 TC 초안(md)
```

파싱·검색·후보 선정·검증·Report 생성은 Python Rule Engine이 담당합니다. 의미적인 변경 영향과 Regression 필요성만 Gemini가 판단하며, 사양서·TC 전체를 통째로 Gemini에 보내지 않습니다.

## 주요 기능

- PDF/Word(`.docx`) 사양서, 다중 시트 TC Excel 자동 파싱
- 기준 사양서와의 실제 diff로 "진짜 변경된 부분"만 분석 (미변경 문장 오탐 방지)
- 제품만 선택하면 등록된 사양서·TC 전체를 자동 검색하는 분석 워크플로, 변경 문서는 여러 개 동시 첨부 가능, 문서 없이 요청 텍스트만으로도 분석 가능
- 사용자 요청 사항이 있으면 BM25로 관련 부분만 추려 Gemini에 보내는 RAG 토큰 절약
- 실제 백엔드 단계 기반 실시간 진행 상태(SSE) — 가짜 퍼센트 없음
- 사용자 관점으로 재구성한 HTML 보고서(의미 단위 Change Summary, 단순화된 TC 표, 사람이 읽는 사양 근거)
- TC ID·Chunk ID 교차검증, Confidence 기반 Manual Review 분류
- 기존 TC로 커버되지 않는 변경에 대한 신규 TC 초안 자동 생성
- VXvue 최신 사양서를 별도 자동화(Polarion 연동)와 연계해 매주 월요일 Windows 작업 스케줄러로 자동 확보, 이전 리비전 자동 정리 (`docs/AUTOMATION.md`)
- 분석 1건당 Gemini 호출 1회 + 동일 입력 재분석 시 캐시로 비용 없음, 일일 토큰 한도 설정 지원
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

앱 실행 후 `/guide`에서 사용법을 바로 확인할 수 있습니다. 서버에 직접 배포하는 상세 절차는 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)를 참고하세요.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Unit Test는 Gemini Mock Response를 사용하므로 API 비용이 발생하지 않습니다.
