# 다른 채팅방에서 사용할 프롬프트

아래 `---` 사이의 내용을 새 채팅(Claude Code 또는 Codex)에 그대로 붙여넣는다.
`이번 작업 목표` 항목만 그때그때 원하는 것으로 바꾼다.

마지막 갱신: 2026-08-31

---

`C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer` 프로젝트 작업을 이어서 수행해줘.

먼저 다음 순서를 반드시 지켜라.

1. 프로젝트 루트의 `AGENTS.md`를 읽는다.
2. `akela/PROTOCOL.md`를 읽고 이번 작업에 맞는 activity로 `akela compile`을 실행한 뒤 slice를 읽는다. `akela` CLI가 설치되어 있지 않으면 그 사실만 보고하고 다음 단계로 넘어간다.
3. `HANDOFF.md`, `README.md`, `SECURITY.md`를 읽는다.
4. `git status`, 최근 commit, 현재 테스트 결과를 확인한다.
5. 서버 작업이 필요하면 먼저 읽기 전용으로 상태와 포트 충돌을 확인한다.

이 프로젝트는 로컬 폴더가 Canonical source이고, 검증된 결과만 Ubuntu 서버 `/home/ubuntu/ai-regression-impact-analyzer`에 배포한다. 공개 GitHub 저장소는 `https://github.com/hongmin3/ai-regression-impact-analyzer`다.

절대 안전 규칙:

- `/home/ubuntu/jjhhub/` 내부에 들어가거나 수정하지 않는다.
- `/mnt/vhdmaster`, `/mnt/vhdmaste`를 수정·이동·삭제·권한 변경·마운트 변경하지 않는다.
- 기존 systemd/nginx/PostgreSQL/방화벽/서비스/virtualenv/requirements/Git 저장소를 변경하지 않는다.
- 기존 서비스를 restart/stop하지 않고 서버를 reboot하지 않는다.
- SSH 비밀번호나 Gemini API Key를 코드, config, README, 로그, Report, Git에 저장하지 않는다. SSH 비밀번호는 파일로 관리하지 않는다는 것이 확정된 방침이다.
- 서버 변경은 `/home/ubuntu/ai-regression-impact-analyzer` 내부로 제한한다.
- 신규 systemd 등록이나 네트워크 설정 변경은 변경안과 영향을 먼저 설명하고 사용자 승인을 받은 뒤 수행한다.

## 현재 상태 (2026-08-31 기준)

구현 완료:

- FastAPI/Jinja2 Web UI, PDF/Excel Parser, BM25 검색, Rule 기반 Candidate Selection
- Gemini Structured Output, Hallucination 검증(실제 TC ID·Chunk ID 교차검증), Confidence 분류
- SQLite Metadata/Cache, HTML Report, CSV Export
- **비밀정보 입력 개선**: `app/core/secrets_loader.py`가 `secrets.txt` / `secrets.json` / `.env` / OS 환경변수를 모두 읽는다. 우선순위는 `OS 환경변수 > secrets.json > secrets.txt > .env > 기본값`. `GET /config/status`와 `POST /config/reload`로 Key 설정 여부 확인과 재시작 없는 재적용이 가능하고, Key 값 자체는 어떤 응답·로그·Report에도 노출되지 않는다.
- 로컬 테스트 `23 passed` (`.\.venv\Scripts\python.exe -m pytest -q`)

확정된 사실:

- SSH는 이미 키 인증으로 동작한다. `ssh -o BatchMode=yes ubuntu@10.13.0.222 'echo ok'`가 성공하므로 배포에 비밀번호가 필요 없다. `~/.ssh/id_ed25519`에 passphrase가 없어 ssh-agent도 필요 없고, Windows `ssh-agent` 서비스는 Stopped/Disabled 상태 그대로 둔다.
- 서버 내부 `/health`는 성공하지만 개발 PC에서 `10.13.0.222:12000` 접속은 Timeout이다. 원인 미규명이며 방화벽/nginx를 임의로 바꾸지 않는다.
- systemd는 아직 등록하지 않았다. 승인 대기안은 `HANDOFF.md` §6에 있다.
- `akela` CLI가 개발 PC에 설치되어 있지 않다. 직전 slice는 knowledge 3개 섹션이 전부 `general-scope`로 dropped되어 비어 있으며, scoping은 사용자 결정으로 보류 중이다.

미해결 / 주의:

- **위 `secrets.txt` 변경분이 아직 서버에 배포되지 않았고 Git에도 커밋되지 않았다.** 작업 전 `git status`로 확인할 것.
- 분석 Job 상태가 `app/web/routes.py`의 `jobs: dict` 메모리에만 있어 재시작 시 사라진다. `analyses` 테이블은 이미 만들어져 있으나 사용되지 않는다.
- Export는 CSV만 있고 XLSX는 없다. openpyxl은 이미 설치되어 있다.
- Gemini 응답의 토큰 usage를 파싱·기록하지 않는다.
- 분석 이력 목록 화면이 없다.
- BM25 인덱스를 등록 시 Chunk 수만 기록하고 직렬화해 재사용하지 않는다.
- FastAPI BackgroundTasks는 대규모 동시 작업용 Queue가 아니다.

## 이번 작업 목표

우선순위 순서다. 이 중 하나 이상을 지정해서 진행한다.

1. 이번 `secrets.txt` 변경분 커밋 및 서버 배포 (`.\scripts\deploy.ps1`), 배포 후 서버 `pytest`와 `/health` 재확인
2. Gemini 응답 토큰 usage 파싱 및 사용량 Logging 보완 (Mock으로 검증, API Key 불필요)
3. Persistent Job 상태 저장 — 기존 `analyses` 테이블을 사용해 재시작 후에도 결과 조회 가능하게
4. XLSX Export 추가 (openpyxl)
5. 분석 이력 목록 화면과 Candidate/Impact 집계 화면 강화
6. TC 컬럼 매핑 설정 UI
7. 실제 사양서/TC/변경 PDF로 Gemini End-to-End 검증 (서버 `secrets.txt`에 Key 입력 선행 필요)
8. 사용자 승인 후 systemd 등록
9. 네트워크 접근 정책 담당자 확인 후 팀원 접속 검증

작업은 가능한 범위에서 직접 구현하고 테스트하되, 기존 운영 시스템 변경이 필요하면 멈추고 승인 요청을 해라. 완료 후 변경 파일, 테스트 결과, 서버 영향, 기존 운영 서비스 변경 여부를 명확히 보고해라.

---
