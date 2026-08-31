# AI Regression Impact Analyzer — 작업 인수인계

## 1. 프로젝트 목적

SW 변경사항 PDF, 제품 사양서/Manual PDF, Test Case Excel을 입력받아 Rule Engine과 Gemini Semantic Decision Engine으로 Regression 검증 TC를 자동 추천한다. 사용자가 ChatGPT/Gemini Web/Claude/Codex에 별도로 질문하지 않는 업무 흐름이 핵심이다.

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
- Knowledge 사양서 PDF 등록
- TC Excel 등록
- PyMuPDF 텍스트 추출 및 Page Chunk
- BM25 Specification 검색
- Rule 기반 Change 분석 및 TC Candidate 축소
- Gemini JSON Schema Structured Output
- 실제 TC ID 및 Specification Chunk ID 교차검증
- Confidence Threshold 분류
- SQLite Metadata/Cache
- Responsive HTML Report와 CSV Export
- Gemini Key를 `secrets.txt` / `secrets.json` / `.env` / OS 환경변수 어디에 넣어도 인식 (우선순위 순)
- `/config/status`, `/config/reload`로 Key 설정 여부 확인 및 재시작 없는 재적용
- 로컬 자동 테스트 `23 passed` (서버 반영 전)
- GitHub Public repository push 완료
- Ubuntu 포트 `12000`에서 임시 사용자 프로세스로 실행 확인

## 5. 현재 남은 작업

우선순위 순서:

1. 이번 변경분(`secrets.txt` 지원)을 서버에 배포 — `.\scripts\deploy.ps1`. 아직 미배포이며 서버는 이전 버전이다.
2. 사용자가 서버 `secrets.txt`에 `GEMINI_API_KEY` 입력 (로컬은 `.env`에 이미 값이 있어 동작 중)
3. 실제 사양서/TC/변경 PDF로 Gemini End-to-End 검증
4. Gemini 응답의 토큰 usage 필드 파싱 및 사용량 Logging 보완 — 미착수
5. Persistent Job 상태 저장 — 미착수. `analyses` 테이블은 이미 있으나 `app/web/routes.py`의 `jobs: dict`가 메모리만 사용한다.
6. XLSX Export 추가 — 미착수. 현재 `app/reports/html_report.py`는 HTML/CSV만 생성한다. openpyxl은 이미 설치되어 있다.
7. UI에서 상세 Candidate/Impact 집계 화면 강화 — 미착수. 분석 이력 목록 화면이 없다.
8. TC 컬럼 매핑 설정 UI 추가 — 미착수
9. 사용자 승인 후 systemd 등록
10. 네트워크 접근 정책 담당자 확인 후 팀원 접속 검증

## 6. systemd 승인 대기안

사용자 승인 전 등록하거나 기존 서비스를 변경하면 안 된다.

- Service Name: `ai-regression-impact.service`
- WorkingDirectory: `/home/ubuntu/ai-regression-impact-analyzer`
- ExecStart: `/home/ubuntu/ai-regression-impact-analyzer/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12000`
- User: `ubuntu`
- Port: `12000`

현재는 systemd가 아닌 일반 사용자 프로세스다. 외부 PC에서 `10.13.0.222:12000` 접속은 Timeout이었고 서버 내부 `/health`는 성공했다. 방화벽/nginx를 임의 변경하지 않는다.

## 7. 운영 서버 절대 보호 규칙

- 기존 서비스 restart/stop 금지
- 서버 reboot 금지
- PostgreSQL, nginx, 방화벽, 기존 virtualenv/requirements 변경 금지
- `/home/ubuntu/jjhhub/` 내부 열람·수정 금지
- `/mnt/vhdmaster`, `/mnt/vhdmaste` 접근·권한·마운트 변경 금지
- 기존 systemd 유닛 변경 금지
- 신규 포트를 사용할 때 `ss -ltnp`로 먼저 재확인
- 서버 변경은 `/home/ubuntu/ai-regression-impact-analyzer` 내부로 제한
- SSH 비밀번호와 Gemini API Key를 코드, Git, README, 로그, Report에 기록하지 않는다.

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

SSH 비밀번호는 어떤 파일에도 저장하지 않는다. 기존 SSH key/agent 인증을 사용한다.

## 10. 작업 완료 시 확인

- `pytest` 통과
- `git diff --check` 통과
- 비밀정보 및 업로드/DB/로그 추적 여부 확인
- 서버 반영 전 포트 재검사
- 배포 후 기존 보호 서비스 `active/running` 재확인
- `akela log applied` 및 `akela log outcome` 수행
- GitHub push 전 공개 가능한 파일만 포함됐는지 재검사

## 11. 알려진 한계

- 실제 Gemini API Key 기반 E2E는 아직 수행되지 않았다.
- `akela` CLI가 개발 PC에 설치되어 있지 않아 `akela compile` / `akela log`를 실행할 수 없다. 직전 slice는 knowledge 3개 섹션이 전부 `general-scope`로 dropped되어 비어 있다. scoping은 보류 결정.
- 현재 작업 상태는 프로세스 메모리에 보관된다.
- XLSX가 아닌 CSV Export만 제공한다.
- Specification Index는 등록 시 Chunk 수를 기록하지만 직렬화된 BM25 인덱스 재사용은 추가 개선이 필요하다.
- FastAPI BackgroundTasks는 대규모 동시 작업용 Queue가 아니다.
