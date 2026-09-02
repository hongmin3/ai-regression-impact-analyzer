# 문서 지도

> 상위: [README](../README.md)

무엇을 하려는지에 따라 읽을 문서가 다르다. 아래 표에서 목적을 먼저 고른다.

## 목적별

| 하려는 일 | 볼 문서 |
|---|---|
| 이 프로젝트가 무엇인지 훑기 | [README](../README.md) |
| **써 보기** — 로컬에 띄우고 분석 1건 돌려보기 | [배포 가이드 §2–3](DEPLOYMENT.md) → 앱 안 `/impact-analyzer/guide` |
| **서버에 올리기** | [배포 가이드](DEPLOYMENT.md) |
| **매뉴얼 서버까지 같이 올리기** | [배포 가이드 §8](DEPLOYMENT.md#8-하위-서비스qa-manual-hub를-같은-서버-manual-hub에-붙이기) |
| **기능 하나를 자세히 알기** | [Regression 영향 분석](modules/impact-analyzer.md) · [매뉴얼 개정 검증](modules/manual-review.md) · [QA Manual Hub](../services/qa-manual-hub/README.md) |
| **새 기능을 추가하기** | [공용 아키텍처](SHARED_PLATFORM_ARCHITECTURE.md) |
| **AI 비용이 왜 이렇게 설계됐는지** | [비용 절감 설계](COST_OPTIMIZATION.md) |
| **에이전트와 개발할 때 폴더·지식을 어떻게 관리하는지** | [Context Engineering](CONTEXT_ENGINEERING.md) |
| **운영 중 문제 대응** | [운영·백업·모니터링](OPERATIONS.md) |
| **추천 정확도 측정** | [정확도 평가](EVALUATION.md) |
| **사양서 자동 동기화 설정** | [자동화 아키텍처](AUTOMATION.md) |
| **비밀정보 취급 규칙** | [SECURITY.md](../SECURITY.md) |

## 사용법은 앱 안에 있다

기능별 사용법은 문서가 아니라 **앱 화면 안**에 둔다. 화면이 바뀌면 같이 바뀌어야 하기
때문이다.

| 주소 | 내용 |
|---|---|
| `/` | 허브 — 기능 선택 |
| `/impact-analyzer/guide` | Regression 영향 분석 사용법 |
| `/manual-review/guide` | 매뉴얼 개정 검증 사용법 |
| `/manual-hub/` | 매뉴얼 서버 (하위 서비스) |
| `/cost-dashboard` | AI 호출·토큰·캐시 사용량 |
| `/config/status` | API Key 설정 여부와 일일 토큰 사용량 (Key 값은 반환하지 않음) |

`/guide`는 하위 호환용으로 남아 있으며 `/impact-analyzer/guide`로 연결된다.

## 전체 문서 목록

### 저장소 루트

| 문서 | 내용 |
|---|---|
| [README.md](../README.md) | 프로젝트 소개, 구성, 설계 배경 |
| [SECURITY.md](../SECURITY.md) | API Key·비밀정보·운영 서버 취급 규칙 |
| [HANDOFF.md](../HANDOFF.md) | 작업 인수인계 기록 |
| [NEXT_STEPS.md](../NEXT_STEPS.md) | 남은 작업 (우선순위 순) |
| [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) | 결정이 필요한 항목 |
| [CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md) | AI 에이전트 작업 규칙 |

### `docs/` — 설계와 운영

| 문서 | 내용 |
|---|---|
| [SHARED_PLATFORM_ARCHITECTURE.md](SHARED_PLATFORM_ARCHITECTURE.md) | 두 가지 확장 방식(모듈 / 하위 서비스), 경계, 추가 체크리스트 |
| [COST_OPTIMIZATION.md](COST_OPTIMIZATION.md) | LLM 호출을 줄이는 9단계 파이프라인 |
| [CONTEXT_ENGINEERING.md](CONTEXT_ENGINEERING.md) | 저장소 관리 기준과 Akela — 작업별 지식 주입으로 컨텍스트 토큰 절감 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 로컬 설치부터 서버 배포, 하위 서비스 통합까지 |
| [OPERATIONS.md](OPERATIONS.md) | 작업 복구, 백업, 상태 모니터링 |
| [EVALUATION.md](EVALUATION.md) | precision·recall·F1 기반 추천 정확도 평가 |
| [AUTOMATION.md](AUTOMATION.md) | 진행 상태 SSE, 사양서 자동 동기화, 보고서 구조 |

### `docs/modules/` — 기능별 상세

| 문서 | 내용 |
|---|---|
| [impact-analyzer.md](modules/impact-analyzer.md) | Regression 영향 분석 — 흐름, 설계 결정, 설정 |
| [manual-review.md](modules/manual-review.md) | 매뉴얼 개정 검증 — 흐름, Human Review Gate, 설정 |

### `services/` — 하위 서비스

| 문서 | 내용 |
|---|---|
| [qa-manual-hub/README.md](../services/qa-manual-hub/README.md) | 매뉴얼 서버 전체 (설치·운영·데이터 모델·보안) |
| [qa-manual-hub/docs/USERGUIDE.md](../services/qa-manual-hub/docs/USERGUIDE.md) | 매뉴얼 서버 사용자·관리자 안내 |

### AI 에이전트용 Knowledge (`knowledge/`)

`akela compile`이 작업 종류에 맞는 부분만 골라 컨텍스트로 주입하는 지식 베이스다. 사람이
읽어야 하는 문서는 위 표에 있고, 이쪽은 에이전트가 쓴다. 동작 방식은
[Context Engineering](CONTEXT_ENGINEERING.md)에 정리했다.

| 파일 | 범위 (scope) |
|---|---|
| `project-overview.md`, `workflow.md` | 모든 작업에 공통 (`all`) |
| `core-architecture.md`, `core-ai-integration.md` | 핵심 앱 코드 작업 (`core-development`) |
| `core-web-ui.md` | 화면 작업 (`web-ui`) |
| `core-testing.md` | 테스트 작업 (`testing`) |
| `core-deployment.md` | 배포·운영 (`deployment`) |
| `core-documentation.md` | 문서 작업 (`documentation`) |
| `manual-hub-*.md` | 하위 서비스 QA Manual Hub (`manual-hub`) |
