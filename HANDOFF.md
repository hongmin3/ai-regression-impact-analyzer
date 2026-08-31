# AI Regression Impact Analyzer — 작업 인수인계

## 1. 프로젝트 목적

SW 변경사항과 제품 사양서/Manual(PDF 또는 Word `.docx`), Test Case Excel을 입력받아 Rule Engine과 Gemini Semantic Decision Engine으로 Regression 검증 TC를 자동 추천한다. 사용자가 ChatGPT/Gemini Web/Claude/Codex에 별도로 질문하지 않는 업무 흐름이 핵심이다.

## 2. 작업 위치

- Canonical source: `C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer`
- Ubuntu 배포본: `/home/ubuntu/ai-regression-impact-analyzer`
- 공개 GitHub: `https://github.com/hongmin3/ai-regression-impact-analyzer`
- 서버 접속: SSH config/key를 사용하며 비밀번호를 파일에 저장하지 않는다.

로컬 소스를 기준으로 개발하고 테스트를 통과한 결과만 서버에 배포한다. 서버 배포 폴더는 Git 저장소가 아닌 일반 디렉터리다.

## 3. 반드시 먼저 읽을 문서

1. `AGENTS.md`
2. `akela/PROTOCOL.md`
3. 해당 activity로 `akela compile`한 slice
4. `README.md`
5. `SECURITY.md`
6. 이 문서

## 4. 현재 구현 상태

- FastAPI/Jinja2 Web UI
- Knowledge 사양서 PDF/Word `.docx` 등록, TC Excel 등록
- 제품/Version을 토글(datalist) 선택 또는 신규 입력으로 관리 (`products`/`product_versions` 테이블, 초기값 VXvue·Bellalun Viewer, 이후 자유롭게 추가)
- Revision은 같은 제품·버전에 등록할 때마다 `Rev.N`으로 자동 증가, 이전 Revision은 삭제되지 않고 이력(레거시)으로 유지 및 다운로드 가능 (`/knowledge/download/{id}`)
- Knowledge 파일 업로드는 클릭 선택과 드래그 앤 드롭 모두 지원 (`app/web/static/app.js`)
- 분석 화면은 사양서/TC를 개별로 고르지 않고 **제품만 선택** → 그 제품에 등록된 사양서·TC를 전부(사양서1~5처럼 서로 다른 문서가 여러 개 등록돼도 이전 문서를 대체하지 않고 전부 유지) 검색 대상으로 사용 (`RegressionAnalyzer.run_for_product`, `Storage.active_documents`)
- PDF/Word `.docx` 텍스트 추출 및 Chunk, BM25 Specification 검색
- Rule 기반 Change 분석이 **등록된 기준 사양서 전체 텍스트와 diff**해 실제 신규/변경 줄만 키워드 매칭 대상으로 사용 (기존에는 변경문서 전체에서 키워드만 추출해 미변경 문장까지 오인하는 문제가 있었음, 2026-08-31 수정)
- Gemini JSON Schema Structured Output에 `draft_test_cases` 포함 — 기존 TC로 커버되지 않는 변경사항은 VXvue TC 가이드 Rev.1.7 §13.1 양식의 신규 TC 초안(md)을 자동 생성 (`output/generated_tc/`), 근거 없는 필드는 반드시 "확인 필요"로 표기 (추가 Gemini 호출 없이 기존 1회 호출에 포함)
- 실제 TC ID 및 Specification Chunk ID 교차검증(신규 TC 초안의 근거 Chunk ID도 동일하게 검증), Confidence Threshold 분류
- SQLite Metadata/Cache, 분석 1건당 Gemini 호출 정확히 1회 + 동일 입력 재분석 시 캐시로 비용 없음
- Responsive HTML Report와 CSV/XLSX Export
- SQLite `analyses` 기반 Persistent Job 상태와 분석 이력/Impact 집계 화면
- 서버 재기동 시 완료 결과는 유지하고 QUEUED/RUNNING 작업은 중단 실패로 명시
- Gemini token usage 파싱·Logging 및 Mock 검증
- VXvue 실제 다중 시트 TC 4개 파싱 확인: 669 / 3,894 / 1,785 / 59건
- 실제 Gemini E2E smoke 성공(파이프라인 검증): 분석 `a4903700e24a`, TC 59, 추천 23, total tokens 54,856
- **실제 서로 다른 문서로 업무 정확도 E2E 검증 완료** (2026-08-31): 기준 사양서 260824(txt→docx 변환, 실사용자 이력) vs 변경문서 260831 PDF(실제 개정판). diff 수정 전 changed_features 20건 중 19건이 실제로는 미변경 문장이었던 것을 확인 → diff 수정 후 3건(모두 진짜 변경)으로 정상화, 추천 29→18건, 토큰 69,737→55,284
- Gemini Key를 `secrets.txt` / `secrets.json` / `.env` / OS 환경변수 어디에 넣어도 인식 (우선순위 순)
- `/config/status`, `/config/reload`로 Key 설정 여부 확인 및 재시작 없는 재적용
- 로컬 자동 테스트 `37 passed` (서버 측은 최신 코드 배포 후 재검증 필요)
- 2026-08-31 서버 배포 완료(구버전 기준), 기존 PID `1208181`은 재시작하지 않았으므로 이번 세션에서 추가된 기능은 아직 서버에 반영되지 않음 — 재배포 필요
- GitHub Public repository push 완료
- Ubuntu 포트 `12000`: `ufw allow 12000/tcp` 적용 후 개발 PC 접속 정상화 (`SECURITY.md` 참고)
- 2026-08-31 사용자 승인 후 서버 프로세스 재시작 완료: 구 PID `1208181`(예전 코드, `GET /analyses` 405) → 신 PID `1214754`(이번 세션 변경분 전체 반영). 동일한 방식(일반 사용자 nohup 프로세스, 포트 `12000`)으로 재시작했고 다른 서비스(5000/5001/5002/5003/8000/10000/18800)는 그대로 유지 확인. stdout/stderr는 `output/logs/uvicorn.out`에 기록

## 5. 현재 남은 작업

우선순위 순서:

1. ~~실제 변경 전용 문서와 서로 다른 기준 사양서를 사용한 업무 정확도 E2E 검증~~ → 완료 (위 4장 참고). 단, 다른 사양서(2~5)·다른 TC Set으로도 추가 검증 권장
2. VXvue Rev.1.7의 원본 개정 표시(취소선/밑줄)·삭제 사양·근거 수준을 결과 모델에 구조화 — 아직 미착수. PDF 서식(취소선 등) 자동 인식은 별도 기술 검토 필요 (`page.get_text('rawdict')` + `get_drawings()` 조합, PyMuPDF에 취소선 플래그가 없어 오탐 가능)
3. 분석 이력의 검색·필터·페이지네이션 보강
4. 자동 탐지로 해결되지 않는 TC용 수동 컬럼/시트 매핑 UI 추가
5. BM25 인덱스 직렬화 및 재사용
6. 사용자 승인 후 최신 서버 코드(이번 세션 변경분 포함) 활성화 또는 systemd 등록 — **재배포 필요**
7. ~~네트워크 접근 정책 담당자 확인 후 팀원 접속 검증~~ → 2026-08-31 `ufw allow 12000/tcp`로 개발 PC 접속은 해결. 다른 팀원 PC 접속 검증만 남음
8. Gemini 일일/세션 토큰 사용량 상한 안전장치 (무료 한도 초과 방지) — 사용자 요청으로 대기 중, 아직 미착수

## 6. systemd 승인 대기안

사용자 승인 전 등록하거나 기존 서비스를 변경하면 안 된다.

- Service Name: `ai-regression-impact.service`
- WorkingDirectory: `/home/ubuntu/ai-regression-impact-analyzer`
- ExecStart: `/home/ubuntu/ai-regression-impact-analyzer/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12000`
- User: `ubuntu`
- Port: `12000`

현재는 systemd가 아닌 일반 사용자 프로세스다. 2026-08-31 `sudo ufw allow 12000/tcp` 적용 후 개발 PC에서 `10.13.0.222:12000` 접속이 정상화됐다 (아래 7장 참고). nginx는 변경하지 않았다.

## 7. 운영 서버 절대 보호 규칙

- 기존 서비스 restart/stop 금지
- 서버 reboot 금지
- PostgreSQL, nginx, 기존 virtualenv/requirements 변경 금지
- 방화벽(`ufw`)은 이 프로젝트가 쓰는 포트(예: `12000`)를 여는 등 이 프로젝트 범위 내 변경만 허용 (2026-08-31 사용자 승인, `SECURITY.md` 반영). 그 외 규칙 변경 금지
- `/home/ubuntu/jjhhub/` 내부 열람·수정 금지
- `/mnt/vhdmaster`, `/mnt/vhdmaste` 접근·권한·마운트 변경 금지
- 기존 systemd 유닛 변경 금지
- 신규 포트를 사용할 때 `ss -ltnp`로 먼저 재확인
- 서버 변경은 `/home/ubuntu/ai-regression-impact-analyzer` 내부로 제한
- Gemini API Key를 코드, Git, README, 로그, Report에 기록하지 않는다. 서버 `sudo` 비밀번호는 `secrets.txt`의 `SERVER_SUDO_PASSWORD`로만 관리하고, 명령 인자·화면·로그·Report·Git에 값 자체를 출력하지 않는다 (자세한 내용은 `SECURITY.md` 참고).

## 8. 개발 및 검증 명령

```powershell
cd "C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer"
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\run.ps1
```

안전 배포:

```powershell
.\scripts\deploy.ps1
```

배포 스크립트는 Git에서 제외된 `.deploy.env`의 Host/User/Target을 사용한다. Password 항목은 만들지 않는다.

SSH는 이미 키 인증으로 동작한다. `ssh -o BatchMode=yes ubuntu@10.13.0.222 'echo ok'`가 성공하므로 배포에 비밀번호가 필요 없다. `~/.ssh/id_ed25519`에 passphrase가 없어 ssh-agent도 필요 없다(Windows `ssh-agent` 서비스는 Stopped/Disabled 상태이며 그대로 둔다). SSH 비밀번호는 어떤 파일에도 저장하지 않으며, 보관이 필요하면 Windows 자격 증명 관리자나 password manager를 쓴다.

서버 확인:

```bash
cd /home/ubuntu/ai-regression-impact-analyzer
.venv/bin/python -m pytest -q
curl -fsS http://127.0.0.1:12000/health
ss -ltnp 'sport = :12000'
```

## 9. 비밀정보 파일

- `secrets.txt`: Gemini API Key 입력용 기본 파일. 메모장으로 열어 `GEMINI_API_KEY=` 뒤에 붙여넣는다. Git 제외
- `secrets.json`: 같은 목적의 JSON 대안. Git 제외
- `.env`: 기존 방식. 계속 동작하며 우선순위는 가장 낮다. Git 제외
- 값 우선순위: OS 환경변수 > `secrets.json` > `secrets.txt` > `.env` > 기본값
- `.deploy.env`: SSH Host/User/Target만 저장, Git 제외
- `secrets.example.txt`, `secrets.example.json`, `.env.example`, `.deploy.env.example`: 값 없는 공개 예제
- `SERVER_SUDO_PASSWORD`: `secrets.txt`에 저장하는 서버(`10.13.0.222`, 사내망 전용) `sudo` 비밀번호. 2026-08-31 사용자 결정으로 도입. 앱은 이 키를 읽지 않으며(`secrets_loader.py` 미인식 키), 서버 운영 자동화(SSH/`sudo -S`)에서만 로컬로 사용한다. 값은 파일 → stdin으로만 전달하고 화면/로그에 출력하지 않는다.

SSH 접속 자체는 여전히 key 인증을 사용한다. 위 `SERVER_SUDO_PASSWORD`는 접속이 아니라 접속 이후의 `sudo` 실행에만 쓰인다.

2026-08-31 기준 로컬과 서버 모두 `secrets.txt` Key 설정이 확인됐다. 서버 파일은 `/home/ubuntu/ai-regression-impact-analyzer/secrets.txt`, 소유자 `ubuntu`, 권한 `600`이다. Key 값 자체는 확인·출력하지 않는다.

## 10. 작업 완료 시 확인

- `pytest` 통과
- `git diff --check` 통과
- 비밀정보 및 업로드/DB/로그 추적 여부 확인
- 서버 반영 전 포트 재검사
- 배포 후 기존 보호 서비스 `active/running` 재확인
- `akela log applied` 및 `akela log outcome` 수행
- GitHub push 전 공개 가능한 파일만 포함됐는지 재검사

## 11. 알려진 한계

- 실제 Gemini smoke E2E는 성공했지만 동일 사양서를 변경/근거 문서로 사용했으므로 업무 정확도 검증은 남아 있다.
- Akela CLI `0.1.4`가 전역 설치되어 compile/applied/outcome 기록이 정상 동작한다.
- 완료된 분석과 상태는 SQLite에 저장되지만 BackgroundTasks 자체는 재시작 후 재개되지 않는다.
- Specification Index는 등록 시 Chunk 수를 기록하지만 직렬화된 BM25 인덱스 재사용은 추가 개선이 필요하다.
- FastAPI BackgroundTasks는 대규모 동시 작업용 Queue가 아니다.
