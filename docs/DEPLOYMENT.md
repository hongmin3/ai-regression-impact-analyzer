# 배포 가이드 — 직접 서버에 구축하기

README는 포트폴리오용으로 핵심만 담고 있어서, 실제로 이 프로젝트를 로컬 또는 서버에
처음부터 구축하려는 사람을 위한 상세 절차를 여기에 정리한다.

## 1. 사전 준비물

- Python 3.11 이상 (서버는 3.12로 검증됨)
- Gemini API Key (https://aistudio.google.com 에서 발급, 무료 한도 존재)
- (서버에 올릴 경우) SSH로 접속 가능한 Linux 서버 — 이 프로젝트는 Ubuntu에서 검증됨
- Git

## 2. 로컬 설치

```powershell
git clone https://github.com/hongmin3/qa-verification-management-system.git
cd qa-verification-management-system
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item secrets.example.txt secrets.txt -Force
notepad secrets.txt   # GEMINI_API_KEY=여기에_키_붙여넣기
```

macOS/Linux는 `.venv/bin/python`을 쓰고, `secrets.example.txt`를 `secrets.txt`로 복사한 뒤 직접
편집하면 된다.

## 3. 로컬 실행 및 확인

```powershell
.\scripts\run.ps1        # http://localhost:12000
```

```bash
./scripts/run.sh         # Linux/macOS
```

브라우저에서 `http://localhost:12000/health`가 `{"status":"ok"}`를 반환하는지, `/impact-analyzer/guide`와 `/manual-review/guide`에서
사용법이 보이는지 확인한다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q   # 59개 테스트, Gemini Mock 사용이라 비용 없음
```

## 4. 서버에 배포하기 (예시: Ubuntu + SSH)

### 4-1. 최초 1회 서버 준비

```bash
ssh your-user@your-server
mkdir -p /path/to/qa-verification-management-system
cd /path/to/qa-verification-management-system
python3 -m venv .venv
```

이 프로젝트는 서버 배포 폴더를 Git 저장소로 두지 않는다 — 로컬에서 검증한 파일만 옮긴다
(레포를 그대로 git clone 해도 무방하지만, 이 프로젝트의 운영 방식은 파일 복사 방식이다).

### 4-2. 배포 스크립트

`.deploy.env.example`을 `.deploy.env`로 복사하고 본인 서버 정보를 채운다 (Git에서 제외됨,
비밀번호는 넣지 않는다 — SSH는 키 인증만 사용):

```text
DEPLOY_SSH_HOST=your-server-ip
DEPLOY_SSH_USER=your-user
DEPLOY_TARGET_DIRECTORY=/path/to/qa-verification-management-system
```

```powershell
.\scripts\deploy.ps1
```

이 스크립트는 로컬 `pytest`를 먼저 통과시키고, `app/`, `scripts/`, `tests/`, `config/`, `docs/`,
`requirements.txt`, `config.yaml`, 예제 파일들만 서버로 복사한다. `secrets.txt`/`.env`/`data/`
같은 개인 설정과 운영 데이터는 복사하지 않는다 (의도적 — 서버의 실제 데이터를 덮어쓰지 않기 위함).

### 4-3. 서버에서 의존성 설치 (새 패키지 추가 시 매번 필요)

```bash
ssh your-user@your-server
cd /path/to/qa-verification-management-system
.venv/bin/pip install -r requirements.txt
```

`deploy.ps1`은 파일만 복사하고 `pip install`은 실행하지 않는다 — `requirements.txt`가 바뀌었으면
반드시 이 단계를 거쳐야 새 패키지(예: APScheduler) 없이 앱이 죽는 것을 막을 수 있다.

### 4-4. 비밀정보 입력 (서버에서 1회)

```bash
cp secrets.example.txt secrets.txt
nano secrets.txt   # GEMINI_API_KEY=...
```

`secrets.txt`/`secrets.json`/`.env`는 Git에도, 배포 스크립트에도 포함되지 않으므로 서버에서
직접 만들어야 한다. 값 우선순위는 OS 환경변수 > `secrets.json` > `secrets.txt` > `.env`이다.

### 4-5. 실행

```bash
cd /path/to/qa-verification-management-system
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12000 > output/logs/uvicorn.out 2>&1 &
disown
curl -fsS http://127.0.0.1:12000/health
```

재배포 후 코드 변경을 반영하려면 같은 포트를 쓰는 기존 프로세스를 종료하고 위 명령으로 다시
띄운다:

```bash
OLD_PID=$(ss -ltnp 'sport = :12000' | grep -oP 'pid=\K[0-9]+')
kill "$OLD_PID"
# 프로세스 종료 확인 후
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12000 > output/logs/uvicorn.out 2>&1 &
disown
```

### 4-6. 방화벽 / 외부 접속

서버가 UFW 등으로 포트별 허용 목록을 쓰는 경우, 사용할 포트를 명시적으로 열어야 한다:

```bash
sudo ufw allow 12000/tcp
sudo ufw status | grep 12000
```

사내망 전용으로 운영한다면 그 서버가 사내망에서만 라우팅되는지 네트워크 담당자에게 확인한다.

## 5. systemd로 상시 서비스화 (선택, 더 견고한 운영)

지금은 일반 사용자 프로세스(`nohup` + `disown`)로 운영해도 동작하지만, 서버가 재부팅되면
자동으로 다시 뜨지 않는다. 상시 운영하려면 systemd 유닛을 등록한다 (아래는 예시이며, 실제 값은
환경에 맞게 바꾼다):

```ini
# /etc/systemd/system/qa-verification-management-system.service
[Unit]
Description=QA 검증 관리 시스템
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/qa-verification-management-system
ExecStart=/path/to/qa-verification-management-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qa-verification-management-system.service
sudo systemctl status qa-verification-management-system.service
```

**주의**: 다른 서비스와 같은 서버를 공유한다면, 기존 systemd 유닛·nginx·방화벽·DB 설정을 건드리지
않고 이 유닛만 새로 추가해야 한다. 운영 서버에 처음 등록할 때는 반드시 서버 관리자(또는 본인이
관리자라면 스스로)에게 영향 범위를 확인한 뒤 진행한다.

## 6. VXvue 사양서 자동 동기화 활성화 (선택)

`docs/AUTOMATION.md`에 상세 설명이 있다. 요약:

1. `config/products/vxvue.yaml`의 `specification.crawler_output_dir`를 실제 크롤러 output 경로로
   맞춘다.
2. 크롤러가 있는 Windows PC에서 `scripts/sync_vxvue_spec.py --target-url http://<서버>:12000`을
   Windows 작업 스케줄러에 매일 등록한다 (서버 자체는 크롤러 폴더에 접근할 수 없어 이 스크립트를
   서버에서 실행할 수 없다).
3. 앱 내부 스케줄러(`app/core/scheduler.py`)는 신규 systemd 없이 이미 함께 뜨며, `/knowledge`
   화면의 "지금 동기화" 버튼으로 수동 실행도 가능하다.

## 7. 업데이트 배포 체크리스트

1. 로컬에서 코드 수정 후 `pytest` 통과 확인
2. `requirements.txt`가 바뀌었으면 §4-3 다시 실행
3. `.\scripts\deploy.ps1`
4. 서버에서 `pytest` 재확인
5. 기존 프로세스 종료 → 재기동 (§4-5) — **다른 서비스나 포트는 건드리지 않는다**
6. `curl http://127.0.0.1:12000/health` 및 주요 페이지(`/`, `/knowledge`, `/analyses`) 확인
