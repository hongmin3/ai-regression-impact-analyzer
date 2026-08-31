# 비밀정보 및 운영 서버 안전 규칙

- Gemini API Key는 프로젝트 루트의 `secrets.txt`, `secrets.json`, `.env` 중 한 곳에만 저장하며 Git, 로그, 보고서에 포함하지 않는다.
- `secrets.txt`, `secrets.json`, `.env`는 `.gitignore` 대상이다. `secrets.example.*`, `.env.example`만 공개한다.
- `/config/status`와 `/config/reload`는 Key 설정 여부, 길이, 출처 이름만 반환하며 Key 문자열은 반환하지 않는다.
- 서버(`10.13.0.222`)는 사내망에서만 접근 가능하다. 사용자 결정에 따라 서버 `sudo` 비밀번호를 프로젝트 루트의 `secrets.txt`에 `SERVER_SUDO_PASSWORD=`로 저장해 관리한다. 사용자가 매번 구두로 전달할 필요가 없도록 하기 위한 것이며, 이 값은 `app/core/secrets_loader.py`가 인식하는 키가 아니므로 FastAPI 앱·`/config/status`·Report에는 절대 노출되지 않는다.
- `SERVER_SUDO_PASSWORD`를 사용하는 자동화는 값을 화면·명령 인자·로그·커밋·대화 응답에 그대로 출력하지 않고, 파일에서 SSH/`sudo -S`의 표준입력으로 곧바로 전달하는 방식만 사용한다.
- 서버 접속은 기존 SSH key 인증을 사용하고, `sudo`가 필요한 작업만 위 방식으로 비밀번호를 전달한다.
- 서버 배포 대상은 `/home/ubuntu/ai-regression-impact-analyzer/`로 제한한다.
- `/home/ubuntu/jjhhub/`, `/mnt/vhdmaster`, `/mnt/vhdmaste` 및 기존 서비스 파일은 열람·수정하지 않는다.
- 기존 systemd, nginx, PostgreSQL 설정은 변경하지 않는다. 방화벽(`ufw`)은 이 프로젝트가 사용하는 포트(예: `12000`)를 여는 등 이 프로젝트 범위 내의 변경만 수행한다.
