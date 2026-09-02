# QA Manual Hub — Agent Instructions

Follow `akela/PROTOCOL.md` for every task.

## Project Root 탐색 규칙

`backend/`, `frontend/`, `deploy/` 등 이 프로젝트 하위 어디서 작업하든 먼저 상위로
`akela.json` 을 탐색해 가장 가까운 Project Root 를 식별하고 그 Root 의 `knowledge/`,
`akela/PROTOCOL.md` 를 사용한다. 하위 디렉터리에 별도 `akela.json` / `knowledge/` 를 만들지
않는다.

경로를 직접 걷어올리기 어려우면 `scripts/find-project-root.ps1` 을 실행해 현재 위치에서
가장 가까운 Project Root 를 확인할 수 있다.
