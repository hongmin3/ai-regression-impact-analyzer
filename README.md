# AI Regression Impact Analyzer

SW 변경사항 PDF, 제품 사양서/Manual PDF, Test Case Excel을 결합해 Regression 검증 대상 TC를 자동 추천하는 내부 QA 업무자동화 서비스입니다. 사용자는 별도의 AI 채팅이나 Prompt 작성 없이 브라우저에서 분석을 실행합니다.

## Architecture

```text
Change PDF → Rule Change Analysis → Specification BM25 Retrieval
           → TC Candidate Selection → Gemini Semantic Decision
           → Schema/Reference/Confidence Validation → HTML + CSV
```

파싱·중복 제거·검색·검증·집계·Report 생성은 Python Rule Engine이 수행합니다. 의미적인 변경 영향, Regression 필요성, 검증 포인트만 Gemini가 판단합니다. 사양서 전체나 TC 전체를 Gemini에 보내지 않습니다.

## 로컬 설치

```powershell
cd "C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env -Force
notepad .env
```

`.env`의 `GEMINI_API_KEY=` 뒤에 Gemini API Key를 입력합니다. `.env`는 Git에서 제외되며 화면·Report·Log에 표시되지 않습니다. SSH 비밀번호는 넣지 않습니다.

## 실행과 종료

```powershell
.\scripts\run.ps1
```

`http://localhost:12000`에 접속합니다. 종료는 실행 창에서 `Ctrl+C`를 누릅니다. Ubuntu에서는 다음을 실행합니다.

```bash
cd /home/ubuntu/ai-regression-impact-analyzer
./scripts/run.sh
```

## 사용 방법

1. `Knowledge` 메뉴에서 제품명, Version, Revision과 사양서/Manual PDF를 등록합니다.
2. 제품명, Version, TC Set Name과 `.xlsx` Test Case를 등록합니다.
3. `분석`에서 변경사항 PDF와 등록된 사양서·TC를 선택합니다.
4. `분석 실행` 후 HTML Report를 열거나 CSV를 내려받습니다.

TC Excel은 `TC ID`, `Category`, `Feature`, `Precondition`, `Step`, `Expected Result`, `Result`, `Remark`와 일반적인 한글/영문 별칭을 인식합니다. `TC ID`는 필수입니다.

## 결과 해석

- `HIGH`: 직접 관련성이 높아 우선 검증 권장
- `MEDIUM`: 직접 또는 중요한 간접 영향 가능성
- `LOW`: 영향 가능성은 낮지만 연관 경로 확인 권장
- `NONE`: 제공된 근거상 영향 없음
- Confidence `0.80 이상`: AI 추천 사용 가능
- `0.60 이상 0.80 미만`: 담당자 Review 권장
- `0.60 미만`: Manual Review 필수

실제 Excel에 없는 TC ID는 폐기되고, 검색된 사양 근거가 없으면 신뢰도를 낮춰 Manual Review로 분류합니다. AI 결과는 최종 QA 판단을 대체하지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Unit Test는 Gemini Mock Response를 사용하므로 API 비용이 없습니다.

## 설정 및 데이터 위치

- 일반 설정: `config.yaml`
- 비밀정보: `.env`
- 앱 DB: `data/app.db`
- 업로드: `data/uploads`, `data/specifications`, `data/testcases`
- 보고서/CSV: `output/reports`, `output/exports`
- 로그: `output/logs/app.log`

Confidence, Top-K, Candidate 수, Retry 횟수는 `config.yaml`에서 변경합니다.

## 문제 해결과 로그

Key 오류는 `.env`, PDF 오류는 텍스트 포함 여부, Excel 오류는 `.xlsx`와 TC ID 컬럼을 확인합니다.

```powershell
Get-Content .\output\logs\app.log -Tail 100
```

```bash
tail -n 100 /home/ubuntu/ai-regression-impact-analyzer/output/logs/app.log
```

업데이트는 로컬 테스트를 통과한 파일만 서버 프로젝트 경로에 복사합니다. 서버의 jjhhub, 기존 systemd/nginx/PostgreSQL, VHD 경로는 변경하지 않습니다. systemd는 Service Name, WorkingDirectory, ExecStart, User, Port를 먼저 제시해 승인받은 뒤 등록합니다.
