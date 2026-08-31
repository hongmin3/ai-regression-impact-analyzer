# 다른 채팅방에서 사용할 연속 작업 프롬프트

아래 `---` 사이를 새 Codex 또는 Claude Code 채팅에 그대로 붙여넣는다. 필요하면 `이번 작업 목표`의 우선순위만 바꾼다.

마지막 갱신: 2026-08-31
현재 Git HEAD: `fed5004` (`origin/master`와 동일)

---

`C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer` 프로젝트 작업을 이어서 수행해줘.

## 시작 순서

다음 순서를 반드시 지켜라.

1. 현재 위치에서 상위로 가장 가까운 `akela.json`을 찾아 Project Root를 확정한다.
2. Project Root의 `AGENTS.md`와 `akela/PROTOCOL.md`를 읽는다.
3. 이번 작업에 맞는 activity로 `akela compile --activity <activity> --task <task-id>`를 실행하고 생성된 slice 전체를 읽는다.
4. `HANDOFF.md`, `README.md`, `SECURITY.md`를 읽는다.
5. `git status`, 최근 commit, 로컬 전체 테스트를 확인한다.
6. 서버 작업 전에는 대상 경로, `/health`, 포트 `12000` 소유 프로세스를 읽기 전용으로 확인한다.

Akela CLI `0.1.4`는 개발 PC에 전역 설치되어 있다. 명령을 찾지 못할 때만 `npx akela@0.1.4 --version`으로 확인하고, 임의의 동명 패키지를 설치하지 않는다.

## 프로젝트와 배포 기준

- Canonical source: `C:\Users\2024980\Documents\자동화\ai-regression-impact-analyzer`
- Ubuntu 배포 경로: `/home/ubuntu/ai-regression-impact-analyzer`
- GitHub: `https://github.com/hongmin3/ai-regression-impact-analyzer`
- 검증된 로컬 결과만 `./scripts/deploy.ps1`로 서버 프로젝트 경로에 배포한다.
- 서버 배포 폴더는 Git 저장소가 아닌 일반 디렉터리다.

## 절대 안전 규칙

- `/home/ubuntu/jjhhub/` 내부에 들어가거나 열람·수정하지 않는다.
- `/mnt/vhdmaster`, `/mnt/vhdmaste`를 접근·수정·이동·삭제하거나 권한/마운트를 변경하지 않는다.
- 기존 systemd/nginx/PostgreSQL/방화벽/서비스/virtualenv/requirements/Git 저장소를 변경하지 않는다.
- 기존 서비스를 restart/stop하지 않고 서버를 reboot하지 않는다.
- SSH 비밀번호나 Gemini API Key를 코드, 설정 예제, 문서, 명령 출력, 로그, Report, Git에 저장하지 않는다.
- SSH 비밀번호 파일을 만들지 않는다. 기존 SSH key 인증만 사용한다.
- 서버 변경은 `/home/ubuntu/ai-regression-impact-analyzer` 내부로 제한한다.
- 신규 systemd 등록, 프로세스 재기동, 네트워크 설정 변경은 변경안과 영향을 먼저 설명하고 사용자 승인을 받은 뒤 수행한다.

## 현재 구현 상태

- FastAPI/Jinja2 Web UI
- PDF 및 Word `.docx` 사양서/변경문서 지원 (`.doc` 미지원)
- VXvue 실제 TC Excel의 Cover/다중 시트/가변 헤더 자동 탐지
- PDF/DOCX text chunk, BM25 사양 검색, Rule 기반 Candidate Selection
- Gemini Structured Output, 실제 TC/Chunk ID 교차검증, Confidence/Manual Review 분류
- Gemini token usage 파싱·Logging
- SQLite Metadata/Cache 및 Persistent Analysis 상태
- 재기동 후 완료 결과 조회, 중단된 QUEUED/RUNNING 작업의 명시적 실패 처리
- 분석 이력 및 Candidate/Impact 집계 화면
- HTML Report, CSV, XLSX Export
- `secrets.txt` / `secrets.json` / `.env` / OS 환경변수 지원
- `GET /config/status`, `POST /config/reload`
- 로컬 및 서버 테스트 `31 passed`

## 검증된 실제 자료

참고 전용 VXvue 지식 폴더:

`C:\Users\2024980\Documents\자동화\VXvue\VXvue 지식파일`

이 폴더는 읽기 전용 참고자료로 사용한다. 원문 PDF/XLSX/TXT나 비밀정보를 공개 Git 저장소에 복사하지 않는다.

- TC 작성 규칙: `[QA 작성 규칙] VXvue TC 설계 및 자체검토 가이드_Rev1.7.md`
- 실제 TC 4개 파싱 성공: 669 / 3,894 / 1,785 / 59건
- 최신 사양서 PDF 6개 파싱 성공
- 실제 Gemini smoke 분석 `a4903700e24a` 성공
  - VXvue 사양서1(260831) PDF + Basic Function Checklist
  - 전체/Candidate/Decision 59건, 추천 23건
  - prompt 22,643 / candidate 12,521 / total 54,856 tokens
  - HTML/CSV/XLSX 생성 및 API Key 패턴 비노출 확인
- 위 smoke test는 동일 사양서를 변경문서와 근거문서로 사용했으므로 파이프라인 검증이며 업무 정확도 검증은 아니다.

VXvue 규칙 적용 시 텍스트 검색 결과만으로 현재 유효 사양을 확정하지 않는다. 최신 유효 사양서, 원본 PDF의 취소선·밑줄·교체 표시, 문서 상태를 확인하고 TC ID와 기존 결과 이력을 보존한다.

## 서버 현재 상태

- SSH key 인증 성공: `ubuntu@10.13.0.222`
- 포트 `12000`: 프로젝트 Python 프로세스 PID `1208181`
- 서버 내부 `http://127.0.0.1:12000/health`: 성공
- 개발 PC에서 `http://10.13.0.222:12000`: TCP/HTTP Timeout
- systemd unit은 아직 없음
- 새 소스는 서버 폴더에 배포됐지만 기존 프로세스를 재시작하지 않아 최신 기능은 실행 중 프로세스에 활성화되지 않았을 수 있다.
- 로컬 및 서버 `secrets.txt`에 Gemini Key가 설정되어 있다.
- 서버 파일은 `/home/ubuntu/ai-regression-impact-analyzer/secrets.txt`, 소유자 `ubuntu`, 권한 `600`이다. Key 값 없이 `/config/status` 또는 `secret_status()`로 설정 여부만 확인한다.

## 이번 작업 목표

우선순위 순서로 가능한 범위를 직접 구현하고 테스트한다.

1. 실제 변경 전용 문서와 별도의 기준 사양서를 사용해 추천 정확도 E2E 검증
2. VXvue Rev.1.7 규칙 반영 강화: 원본 개정 표시/삭제 사양/근거 수준을 결과 모델에 구조화
3. 분석 이력 검색, 상태·날짜 필터, 페이지네이션
4. 자동 탐지 실패용 TC 시트/헤더 수동 매핑 UI
5. BM25 인덱스 직렬화 및 재사용
6. BackgroundTasks의 동시 작업 한계 보완을 위한 Queue 설계
7. 사용자 승인 후 최신 서버 코드 활성화 또는 systemd 등록
8. 네트워크 담당자 확인 후 개발 PC/팀원 웹 접속 검증

운영 시스템 변경이 필요하면 멈추고 승인 요청을 한다. 완료 후 변경 파일, 테스트 결과, Gemini 비용/usage, 서버 영향, 기존 서비스 변경 여부, Git commit/push, Akela applied/outcome을 명확히 보고한다.

---
