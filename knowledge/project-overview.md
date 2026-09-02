## 목적
<!-- akela: id=purpose scope=all tier=must -->

SW 변경사항, 제품 사양서/Manual, TC Excel을 분석해 Regression 검증 TC와 근거를 자동 추천한다. 사용자가 별도 AI 채팅에 질문하지 않는 업무 흐름이 핵심이다.

## 주요 구성
<!-- akela: id=components scope=core-development tier=should -->

FastAPI UI, PDF/Excel Parser, BM25 Retriever, Rule Candidate Selector, Gemini Structured Decision, Validation Engine, HTML/CSV Report, SQLite Storage로 구성한다.

## 운영 격리
<!-- akela: id=production-isolation scope=deployment tier=must -->

서버에서는 `/home/ubuntu/ai-regression-impact-analyzer`만 사용한다. 기존 jjhhub, systemd, nginx, PostgreSQL, VHD 경로를 변경하지 않으며 서비스 등록은 사용자 사전 승인 후에만 수행한다.
