# 핵심 앱 — 화면 구조 규칙

## 템플릿 상속
<!-- akela: id=template-inheritance scope=web-ui tier=must -->

- 공용 골격은 `app/web/templates/base.html` 하나다. 블록은 `page_title`, `header_title`, `header_subtitle`, `header_nav`, `main_class`, `content`.
- 각 모듈은 자기 `templates/module_base.html`에서 `base.html`을 상속하고 **자기 내비게이션만** 채운다. 모듈 화면은 그 module_base를 상속한다.
- 허브(`hub.html`)는 `header_nav`를 비운다 — 기능 선택 화면에는 내비게이션이 없다.
- 새 모듈을 만들면 `app/modules/<name>/templates/module_base.html`을 함께 만든다. 공용 `base.html`에 모듈 전용 요소를 추가하지 않는다.

## 기능 간 링크를 공용 레이아웃에 섞지 않는다
<!-- akela: id=module-navigation-rule scope=web-ui tier=must -->

- 각 모듈은 자기 내비게이션과 자기 사용법(`/<module>/guide`)을 소유한다.
- 모듈 A의 화면에서 모듈 B로 가는 링크를 공용 헤더에 넣지 않는다. 기능 사이 이동은 허브(`/`)를 거친다.
- 허브로 돌아가는 링크만 각 모듈 내비게이션에 둔다.

## 허브의 하위 서비스 카드
<!-- akela: id=hub-service-cards scope=web-ui tier=should -->

- 허브 카드는 두 종류다. in-process 모듈은 템플릿에 직접 쓰고, 별도 배포 단위는 `config.yaml`의 `services.<name>`(name/description/url)에서 읽어 렌더링한다.
- `url`이 비면 카드를 만들지 않는다 — 그 서비스를 배포하지 않은 환경에서 깨진 링크가 노출되지 않게 하기 위해서다.
- `url`이 상대 경로면 nginx가 그 경로를 프록시한다는 뜻이다. 앱 포트로 직접 들어온 같은 경로 요청은 포트 없는 같은 호스트로 307 리다이렉트한다(`app/web/router.py::service_fallback`). 명시적 포트가 없는 요청은 리다이렉트하지 않는다 — 무한 루프가 된다.

## 진행 상태는 실제 백엔드 단계다
<!-- akela: id=progress-sse scope=web-ui tier=must -->

- 진행률은 SSE(`text/event-stream`)로 보내며 **실제 백엔드 단계 인덱스**를 그대로 쓴다. 시간이 지나면 올라가는 가짜 퍼센트를 만들지 않는다.
- 응답 헤더에 `Cache-Control: no-cache`와 `X-Accel-Buffering: no`를 넣는다. 없으면 nginx가 버퍼링해 화면이 멈춘 것처럼 보인다.
- 단계 정보의 출처는 `Storage.update_stage`가 기록한 값이다. 화면에서 단계를 새로 만들지 않는다.

## 정적 파일
<!-- akela: id=static-assets scope=web-ui tier=should -->

- `/static`에 `app.css`와 `app.js` 각각 하나뿐이다. 빌드 도구·프레임워크를 쓰지 않는다.
- CSS는 한 줄로 압축돼 있다. 규칙을 추가할 때 기존 셀렉터 뒤에 이어 붙이고 파일을 재포맷하지 않는다.

## 사용법은 앱 안에 둔다
<!-- akela: id=guide-pages scope=web-ui tier=should -->

- 기능별 사용법은 문서가 아니라 화면(`/impact-analyzer/guide`, `/manual-review/guide`)에 있다. 화면이 바뀌면 같이 바뀌어야 하기 때문이다.
- `/guide`는 하위 호환용이며 `/impact-analyzer/guide`로 308 리다이렉트된다.
- 새 모듈을 만들면 `guide.html`을 함께 만든다.

## 감사 화면
<!-- akela: id=audit-view scope=web-ui tier=should -->

분석 상세 화면은 요청 문서, Knowledge 근거, System Instruction, Gemini에 실제로 전달된 입력 JSON과 원본 응답, 모델·캐시·생성 설정, BM25 후보 순위·점수를 그대로 보여준다. 이 화면이 이 서비스의 감사 근거이므로, AI 호출 경로를 바꾸면 여기에 남는 정보도 함께 유지한다.
