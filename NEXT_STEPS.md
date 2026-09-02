# Next Steps — 매뉴얼 개정 검증 기능 진행 상황 (우선순위 순)

과거 완료 작업의 상세 서사(무엇을 왜 어떻게 고쳤는지)는 git log와 각 커밋 메시지에 있다.
이 파일은 "아직 할 일"을 우선순위 순으로 추적하는 문서이므로, 완료된 항목은 날짜·한 줄
요약·커밋 해시만 남긴다(2026-09-02 압축 — 토큰 절약 목적, 상세가 필요하면
`git log --grep`/`git show <hash>`).

## 완료 이력 색인 (최신순, 상세는 커밋 참고)

- 2026-09-02: Release Scope BM25 소표본 오탐 완화(토큰 겹침 fallback) — `63fbd11`
- 2026-09-02: Word Comment 앵커링을 문단 단위→변경 요소 단위로 정밀화 — `f5c4f9f`
- 2026-09-02: `app/parsers/*` 계층 역전 해소(`app/core/document_schemas.py`) — `dee64c2`
- 2026-09-02: `deploy.ps1` 자동 pip install + `-Restart` 옵션 — `15f1d05`
- 2026-09-02: nginx HTTPS 강제 적용(self-signed) + 구주소 호환 블록 제거 — `e887bc7`
- 2026-09-02: Akela 첫 CURATE 검토 + `core-deployment.md` 갱신 — `a4fca4c`
- 2026-09-02: 구 GitHub 저장소(`qa-manual-hub`) archive 처리
- 2026-09-02: 운영 신뢰성/평가 CLI/CI/백업/PDF 개정 표시 고도화 — `7d8f854`, `611e4a9`
- 2026-09-02: 등록 문서 파싱 결과 캐시 — `c60380c`
- 2026-09-02: systemd 전환, 모니터 확장(nginx/manual_hub), cron 시간대 정정, 매뉴얼 서버
  데이터 연동(Cross-Manual 대조 소스로 활용, 실서버 활성화까지 완료)
- 2026-09-01: TC Excel 컬럼/시트 수동 매핑 UI — `4459dd3`
- 2026-09-01: 분석 이력 검색·필터·페이지네이션 — `7b38ac5`
- 2026-09-01: 매뉴얼 개정 검증 캐시 Hit 기록(비용 대시보드 공백 해소) — `af0287a`
- 2026-09-01: 실제 파일 기반 E2E pytest 편입 — `458dbd3`
- 2026-09-01: 비용/캐시 대시보드 UI(`/cost-dashboard`) — `c674185`
- 2026-09-01: Cross-Manual 영향분석, 이미지 변경 Human Review Gate, 프로젝트 명칭 통일
  (표시명 "QA 검증 관리 시스템", slug `qa-verification-management-system`)
- 2026-09-01: QA 플랫폼 허브 전환, 공용 Knowledge 모듈 분리, PDF 리비전 diff, Release
  Note/설계검토보고서 상세 근거, 매뉴얼 개정 검증 최초 구현(스켈레톤→파이프라인), Release
  Note 파서 + Reverse 검증(누락 의심)

## 아직 미착수 (2026-09-02 재정리, 우선순위 순)

각 항목의 "확인" 줄은 실서버 또는 로컬에서 직접 검증한 근거다.

### A. 운영 리스크

1. **매뉴얼 서버 백업이 원본과 같은 디스크에 있다.** 실서버 조사 확인(2026-09-02): 물리
   디스크가 `sda` 하나뿐이고 `/`·`/home`이 같은 btrfs subvolume이다. `/srv/qa-manual-hub/
   backup`(276M)과 `storage`(58M) 모두 `/dev/sda3` 위에 있어 디스크 장애 시 함께 소실된다.
   `/mnt/vhdmaster`가 별도 마운트로 있지만 운영 보호 규칙상 접근·마운트 변경 금지 대상이라
   쓸 수 없다. **여분 디스크가 없어 이 서버만으로는 해결 불가 — 별도 볼륨/NAS 추가라는
   인프라 결정이 먼저 필요하다** (보류, 사용자 결정 대기).

### B. 제품 기능 고도화

9. **`retrieval.candidate_limit=150`이 검증되지 않았다.** 실서버 표본 1건(전체 TC 6,407 →
   후보 150 → 최종 추천 3)만으로 정한 값이다. 추천 정확도 측정 루프는 이미 동작하지만
   (완료된 분석 상세 화면에서 QA 확정 TC ID/메모 적립 → precision/recall/F1 표시), QA
   확정 표본이 실제로 쌓여야 조정 근거가 생긴다.
12. **매뉴얼 서버 확장 항목.** 본문 full-text 검색(현재 PostgreSQL ILIKE → `tsvector`),
    변경 알림(Email/Teams), Revision 자동 추출, 권한 고도화. 구조는 준비돼 있고 미구현이다
    (`services/qa-manual-hub/README.md` "향후 확장").

### C. 구조 · 기술 부채

14. **핵심 앱 스키마 마이그레이션 방식.** 현재 `CREATE TABLE IF NOT EXISTS` + 컬럼 보강이다.
    `docs/SHARED_PLATFORM_ARCHITECTURE.md`가 정한 전환 시점(운영 인스턴스나 개발자 증가)에
    도달하면 Alembic으로 옮긴다. 매뉴얼 서버는 이미 Alembic을 쓴다.

### D. Akela 지식 운영

19. **매뉴얼 서버 지식 31개 섹션이 아직 한 번도 applied되지 않았다.** 병합하며 편입만 했고
    그 activity로 실제 작업을 한 적이 없다. 다음 매뉴얼 서버 작업 때 실제로 쓸모가 있는지
    검증해야 한다.
20. **CURATE 정기 검토** 1차는 2026-09-02에 완료(`deployment`/`core-development` 스코프,
    커밋 `a4fca4c`)했지만 다음 정기 실행은 아직 예약되지 않았다. 주기적 실행(주 1회 또는
    스프린트당 1회)을 원하면 `/loop` 또는 스케줄 작업으로 등록. `scope=all`+`tier=should`
    전체 스코프 검토는 아직 한 적 없다.

## 알려진 설계상 단순화 (버그 아님, 의도적 v1 범위)

- `match_release_changes`의 BM25 매칭은 토큰 겹침 fallback(2026-09-02)으로 소표본 오판을
  줄였지만, 여전히 로컬 규칙 기반 참고 신호일 뿐 확정 판정이 아니다 — 항상 "QA 확인 필요"로
  취급할 것.
- 매뉴얼 서버 Cross-Manual 연동은 제품 **이름**으로 매칭한다. 현재 겹치는 제품은
  `Bellalun Viewer` 하나뿐이고, 핵심 앱의 `VXvue`는 매뉴얼 서버에 같은 이름의 제품이 없어
  조용히 건너뛴다(오류 아님). VXvue도 대조에 쓰려면 매뉴얼 서버에 `VXvue` 제품을 만들고
  매뉴얼을 등록해야 한다.
