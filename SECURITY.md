# 비밀정보 및 운영 서버 안전 규칙

- Gemini API Key는 프로젝트 루트의 `secrets.txt`, `secrets.json`, `.env` 중 한 곳에만 저장하며 Git, 로그, 보고서에 포함하지 않는다.
- `secrets.txt`, `secrets.json`, `.env`는 `.gitignore` 대상이다. `secrets.example.*`, `.env.example`만 공개한다.
- `/config/status`와 `/config/reload`는 Key 설정 여부, 길이, 출처 이름만 반환하며 Key 문자열은 반환하지 않는다.
- SSH 비밀번호는 파일, 환경변수, 스크립트, 명령 인자에 저장하지 않는다.
- 서버 접속은 기존 SSH key 또는 SSH agent 인증을 사용한다.
- 서버 배포 대상은 `/home/ubuntu/ai-regression-impact-analyzer/`로 제한한다.
- `/home/ubuntu/jjhhub/`, `/mnt/vhdmaster`, `/mnt/vhdmaste` 및 기존 서비스 파일은 열람·수정하지 않는다.
- 기존 systemd, nginx, PostgreSQL, 방화벽 설정은 변경하지 않는다.
