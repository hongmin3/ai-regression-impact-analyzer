# Context Engineering — 저장소의 기준과 Akela

> 상위 문서: [README](../README.md) · [문서 지도](README.md)

이 저장소는 AI 에이전트(Claude Code / Codex)와 함께 개발한다. 그때 실제로 발목을 잡는 것은
모델 성능이 아니라 **컨텍스트**다. 매 작업마다 저장소 문서를 통째로 넣으면 두 가지가 같이
나빠진다.

- **토큰** — 작업 1건마다 전체 문서를 읽으니 비용이 작업 수에 비례해 늘어난다.
- **정확도** — 지금 하는 일과 무관한 문서가 섞여 들어와 엉뚱한 파일을 고친다.

해결은 두 단계다. 먼저 **폴더에 기준을 만들고**, 그 기준을 이용해 **작업에 필요한 지식만
잘라서 준다.** 앞의 것이 없으면 뒤의 것을 할 수 없다.

---

## 1단계 — 폴더를 일정한 기준으로 관리한다

"어디에 무엇이 있는지"가 규칙으로 정해져 있어야, 에이전트가 전부 읽지 않고도 필요한 곳을
찾는다. 이 저장소가 지키는 기준은 다음과 같다.

| 기준 | 내용 | 근거 문서 |
|---|---|---|
| 배포 단위는 둘뿐 | `app/`(핵심 앱)과 `services/*`(하위 서비스). 새 기능은 어느 쪽인지 먼저 정한다 | [공용 아키텍처](SHARED_PLATFORM_ARCHITECTURE.md) |
| 기능은 자기 폴더가 전부 소유 | `app/modules/<name>/`이 라우터·스키마·서비스·템플릿·테스트를 갖는다. `app/web/`은 URL prefix만 결정하고 로직을 갖지 않는다 | 같은 문서 |
| 하위 서비스는 결합하지 않는다 | 코드 import·DB 공유 없음. 연결은 URL 링크와 nginx 라우팅까지 | 같은 문서 |
| 지식은 루트 한 곳 | 하위 서비스도 `knowledge/`를 따로 만들지 않고 `knowledge/<name>-*.md`로 모은다 | [CLAUDE.md](../CLAUDE.md) |
| 문서는 목적별 | `docs/README.md`가 지도. 기능별 사용법은 문서가 아니라 앱 화면 안에 둔다 | [문서 지도](README.md) |
| 테스트 경계 | 루트 `pytest`는 `testpaths`로 핵심 앱만 수집. 하위 서비스는 자기 CI에서 | `pytest.ini` |
| 프롬프트는 한 곳 | `app/prompts/*.yaml`이 본문·버전·생성 설정을 함께 갖는다 | [비용 절감 설계](COST_OPTIMIZATION.md) |

이 규칙들을 사람이 기억하는 대신 [`CLAUDE.md`](../CLAUDE.md) / [`AGENTS.md`](../AGENTS.md)에
적어 두고, 에이전트가 매 작업 전에 읽는다.

---

## 2단계 — Akela로 작업 종류별 지식만 주입한다

[Akela](https://github.com/TimothyHan/akela)는 지식 문서를 **섹션 단위로 쪼개고, 각 섹션에
`scope`(어떤 작업에 필요한가)와 `tier`(얼마나 중요한가)를 태깅**해 두었다가, 작업 종류에 맞는
부분만 뽑아 컨텍스트로 주는 도구다. **런타임 의존성이 아니다** — 앱 실행·배포 동작에 전혀
영향을 주지 않는다.

### 태깅

```markdown
## Product → Document → Revision 계층 구조
<!-- akela: id=manual-hub-hierarchy scope=manual-hub tier=must -->
```

- `scope=all` — 모든 작업에 들어간다
- `scope=manual-hub` — 매뉴얼 서버 작업에만 들어간다
- `tier=must` / `should` — 컨텍스트가 빠듯할 때 무엇을 먼저 버릴지의 순서

### 작업 흐름

```text
knowledge/*.md
  ↓  akela compile --activity <activity> --task <task-id>
.akela/runs/<run>/slice.md      이 작업에 필요한 섹션만 (나머지는 dropped 로 기록)
  ↓  에이전트가 slice 만 읽고 작업
akela log applied <source-id>          근거로 실제 사용한 규칙
akela log contradicted <source-id>     결과가 뒤집은 규칙 (틀린 내용을 원문 인용과 함께)
akela log outcome --status DONE
  ↓  akela stats / akela/CURATE.md
지식 유지보수      안 쓰이는 규칙은 좁히거나 버리고, 틀린 규칙은 고친다
```

절차의 정본은 [`akela/PROTOCOL.md`](../akela/PROTOCOL.md)(작업), 
[`akela/ONBOARD.md`](../akela/ONBOARD.md)(새 지식 편입),
[`akela/CURATE.md`](../akela/CURATE.md)(정기 검토)다.

### 실제로 주입되는 slice

`core-development` 작업 하나의 실제 컴파일 결과(`.akela/runs/*/slice.md`)다. 전체 1.1KB이며,
쓰인 것과 **버려진 것과 그 이유**까지 남는다.

```yaml
compiler: akela 0.1.4   domain: default
sources:
  - id: REF-project-overview#purpose      tier: must   lines: 2
  - id: REF-workflow#execution-flow       tier: must   lines: 2
dropped:
  - id: REF-project-overview#components   reason: general-scope
  - id: REF-troubleshooting#known-issues  reason: general-scope
  - id: REF-troubleshooting#check-order   reason: general-scope
  - id: REF-workflow#rerun-caveats        reason: general-scope
```

---

## 이 저장소의 실제 구성

| 항목 | 값 |
|---|---|
| 지식 파일 | 7개 (`knowledge/*.md`) |
| 섹션 | 38개 · 약 27KB |
| scope 분포 | `all` 6 · `deployment` 1 · `manual-hub` 31 |
| tier 분포 | `must` 19 · `should` 19 |
| activity | `core-development`, `web-ui`, `testing`, `deployment`, `documentation`, `manual-hub` |
| 기록된 작업 | 31건 (`.akela/runs/`) |
| 근거 사용 기록 | `applied` 56건 · `contradicted` 1건 (`akela/learnings-log.jsonl`) |

**핵심 효과.** 지식 베이스는 27KB지만 회귀 분석 쪽 작업에 실제로 들어가는 slice는 1.2KB
안팎이다. 매뉴얼 서버 지식 31개 섹션(약 25KB)은 `scope`가 달라 애초에 컴파일되지 않는다.

## 저장소를 합칠 때 이 기준을 어떻게 적용했나

QA Manual Hub를 `services/qa-manual-hub/`로 병합할 때, 원래 저장소에 있던
`akela.json`·`knowledge/`·`akela/`를 **그대로 가져오지 않았다.** 하위 폴더에 별도 Project
Root가 생기면 에이전트가 어느 Context를 써야 하는지 모호해지고, 두 지식 베이스가 서로를
모른 채 쌓인다.

대신:

1. `services/qa-manual-hub/knowledge/*.md` → 루트 `knowledge/manual-hub-*.md`로 이동
2. 31개 섹션 전부에 `scope=manual-hub`와 `tier`를 부여
3. `akela.json`의 `activities`에 `manual-hub` 추가
4. 하위의 `akela.json` / `akela/` 삭제, `AGENTS.md` / `CLAUDE.md`는 루트를 가리키는 안내로 대체

결과적으로 **저장소가 커져도 회귀 분석 작업의 컨텍스트 크기는 그대로다.** 지식이 늘어난
만큼 토큰이 늘지 않는다. 새 하위 서비스를 추가할 때도 같은 순서를 따른다
([공용 아키텍처](SHARED_PLATFORM_ARCHITECTURE.md)의 하위 서비스 체크리스트).

## 새 지식을 추가할 때

1. 관련 `knowledge/*.md`에 섹션을 쓰고 `<!-- akela: id=… scope=… tier=… -->`를 붙인다.
2. scope를 못 정하겠으면 태그 없이 두어도 된다. `akela stats`가 `unscoped`로 보고하고,
   [`akela/ONBOARD.md`](../akela/ONBOARD.md) 절차로 나중에 범위를 정한다.
3. `scope=all`은 아껴 쓴다. 모든 작업의 slice에 들어가므로 매 작업마다 비용을 낸다.
4. 새 하위 서비스라면 `<name>-*.md` 이름과 `scope=<name>`, 그리고 `akela.json`에 activity 추가.

## 한계

- Akela는 **에이전트용 지식**만 다룬다. 사람이 읽는 문서는 `docs/`에 따로 있고, 둘은 목적이
  다르다. 같은 내용을 양쪽에 중복해 두지 않는다.
- 태깅이 실제와 어긋나면 잘못된 지식이 계속 주입된다. 그래서 `applied` / `contradicted`
  기록을 남기고 [`akela/CURATE.md`](../akela/CURATE.md)의 정기 검토로 교정한다.
- 지식이 늘수록 `scope=all` 섹션이 늘어나기 쉽다. 검토에서 가장 먼저 보는 항목이다.
