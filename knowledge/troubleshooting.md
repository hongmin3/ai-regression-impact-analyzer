## 알려진 이슈
<!-- akela: id=known-issues scope=all tier=should -->

Gemini Key가 없으면 실제 분석은 실패하지만 Web 서비스는 유지된다. Python 3.14 개발 환경에서는 PyYAML 6.0.3 및 Pydantic 2.12.5 이상이 필요하다.

## 점검 순서
<!-- akela: id=check-order scope=all tier=should -->

Health endpoint → app.log → 입력 형식 → TC ID 컬럼 → `.env` Key → Gemini Rate Limit/Timeout → 검색 Chunk 존재 여부 순서로 확인한다.
