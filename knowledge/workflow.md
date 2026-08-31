## 실행 흐름
<!-- akela: id=execution-flow scope=all tier=must -->

Knowledge 등록 → Change PDF Upload → Rule 분석 → 사양 Top-K 검색 → TC 후보 축소 → Gemini 의미 판단 → ID/Schema/Confidence 검증 → HTML/CSV 생성 순서로 실행한다.

## 반복 작업 시 주의사항
<!-- akela: id=rerun-caveats scope=all tier=should -->

동일 AI 입력은 SQLite Cache를 재사용한다. 업로드·DB·인덱스·로그·보고서는 Git에 포함하지 않는다. Unit Test는 Gemini Mock을 사용한다.
