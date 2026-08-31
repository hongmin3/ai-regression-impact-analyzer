# 다른 채팅방에서 사용할 프롬프트

아래 내용을 새 Codex 채팅에 그대로 붙여넣는다.

---

`C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer` 프로젝트 작업을 이어서 수행해줘.

먼저 다음 순서를 반드시 지켜라.

1. 프로젝트 루트의 `AGENTS.md`를 읽는다.
2. `akela/PROTOCOL.md`를 읽고 이번 작업에 맞는 activity로 `akela compile`을 실행한 뒤 slice를 읽는다.
3. `HANDOFF.md`, `README.md`, `SECURITY.md`를 읽는다.
4. `git status`, 최근 commit, 현재 테스트 결과를 확인한다.
5. 서버 작업이 필요하면 먼저 읽기 전용으로 상태와 포트 충돌을 확인한다.

이 프로젝트는 로컬 폴더가 Canonical source이고, 검증된 결과만 Ubuntu 서버 `/home/ubuntu/ai-regression-impact-analyzer`에 배포한다. 공개 GitHub 저장소는 `https://github.com/hongmin3/ai-regression-impact-analyzer`다.

절대 안전 규칙:

- `/home/ubuntu/jjhhub/` 내부에 들어가거나 수정하지 않는다.
- `/mnt/vhdmaster`, `/mnt/vhdmaste`를 수정·이동·삭제·권한 변경·마운트 변경하지 않는다.
- 기존 systemd/nginx/PostgreSQL/방화벽/서비스/virtualenv/requirements/Git 저장소를 변경하지 않는다.
- 기존 서비스를 restart/stop하지 않고 서버를 reboot하지 않는다.
- SSH 비밀번호나 Gemini API Key를 코드, config, README, 로그, Report, Git에 저장하지 않는다.
- 서버 변경은 `/home/ubuntu/ai-regression-impact-analyzer` 내부로 제한한다.
- 신규 systemd 등록이나 네트워크 설정 변경은 변경안과 영향을 먼저 설명하고 사용자 승인을 받은 뒤 수행한다.

현재 MVP에는 FastAPI UI, PDF/Excel Parser, BM25 검색, Rule 기반 Candidate Selection, Gemini Structured Output, Hallucination 검증, Confidence 분류, SQLite Cache, HTML Report, CSV Export가 구현되어 있고 로컬/서버 테스트는 9개 통과했다. 서버 내부 `/health`는 성공했지만 개발 PC에서 `10.13.0.222:12000` 접속은 Timeout이었다. systemd는 아직 등록하지 않았다.

이번 작업 목표: [여기에 다음 작업을 구체적으로 적는다]

작업은 가능한 범위에서 직접 구현하고 테스트하되, 기존 운영 시스템 변경이 필요하면 멈추고 승인 요청을 해라. 완료 후 변경 파일, 테스트 결과, 서버 영향, 기존 운영 서비스 변경 여부를 명확히 보고해라.

---
