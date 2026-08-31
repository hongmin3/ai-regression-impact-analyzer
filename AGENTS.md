# AGENTS.md — ai-regression-impact-analyzer

SW 변경사항과 제품 사양서 및 Test Case를 분석하여 Regression 검증 대상을 자동 추천하는 QA 업무자동화 서비스

## Akela Context

Follow `akela/PROTOCOL.md` for every task.

## Project Root 탐색

이 프로젝트 하위 어디에서 작업하든(예: `src/`, `scripts/`, `tests/`) 먼저 현재 위치에서 상위로 `akela.json`을 탐색해 가장 가까운 Project Root를 식별하고, 그 Root의 `knowledge/`·`akela/PROTOCOL.md`를 사용한다. 하위 디렉터리에 별도 `akela.json`/`knowledge/`를 새로 만들지 않는다. 필요하면 `scripts/find-project-root.ps1`을 사용한다.

이 프로젝트를 Workspace 밖에서 단독으로 Clone해도 이 파일과 `akela.json`/`knowledge/`만으로 동일하게 동작해야 한다 (상위 Workspace 경로에 대한 의존성 없음).
