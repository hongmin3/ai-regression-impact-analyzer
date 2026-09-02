# QA Manual Hub — Data Model

> 이 문서의 저장소 상대 경로(`backend/`, `frontend/`, `deploy/` 등)는 모두
> `services/qa-manual-hub/` 기준이다. `<APP_ROOT>` / `<DATA_ROOT>` 는 서버의
> 런타임 경로이며 저장소 경로가 아니다.


## Product → Document → Revision 계층 구조
<!-- akela: id=manual-hub-hierarchy scope=manual-hub tier=must -->

```
Product
 └ Document
    ├ Revision A
    ├ Revision B
    ├ Revision C
    └ Revision D  ← CURRENT
```

- 제품 → 문서 → 버전 → 파일의 4계층 구조.
- **Product**: 제품. 화면에서 자유롭게 추가 (예: Bellalun Viewer, VXvue).
- **Document**: 문서 종류 (예: Operation Manual, Service Manual, QC Manual). 같은 제품 안에서
  같은 이름의 문서는 만들 수 없다(대소문자 무시). 다른 제품에는 같은 이름을 쓸 수 있다.
- **Version / Revision**: 문서의 한 개정본. 실제 파일 1개가 붙는다. 형식을 강제하지 않는다 —
  `V1.0.12W1`, `Rev.1.3`, `R2`, `2026.07`, `1.1` 을 문서에 적힌 그대로 입력한다. Version 과
  Revision 중 최소 하나는 반드시 입력해야 한다.
- **Current**: 그 문서의 현재 최신본. 문서마다 딱 하나. 새 버전 업로드 시 자동으로 Current
  지정되며, 과거 Legacy 문서를 뒤늦게 올린 경우 "Set as Current" 로 원하는 버전을 복구할 수 있다.
  Current 를 바꿔도 다른 버전은 삭제되지 않는다.

## 테이블 관계 (11개 테이블)
<!-- akela: id=manual-hub-table-relations scope=manual-hub tier=should -->

```
users ─────┬──< sessions
           ├──< login_history
           ├──< products ──────┬──< documents ──┬──< document_versions
           ├──< document_categories ────────────┘         │
           ├──< stored_files <────────────────────────────┘
           ├──< audit_logs
           └──< system_settings
```

상세 컬럼은 `backend/app/models.py` 와 `backend/alembic/versions/0001_initial_schema.py` 에 있다.

## 핵심 설계 결정
<!-- akela: id=manual-hub-design-decisions scope=manual-hub tier=must -->

- **Current 는 `documents.current_version_id` 단일 컬럼.** 버전 쪽에 `is_current` 를 두면
  "동시에 두 개가 Current" 상태가 물리적으로 가능해진다. 문서 행의 컬럼 하나로 두면 그 상태를
  표현할 방법이 없다. 변경 시 `SELECT ... FOR UPDATE` 로 문서 행을 잠그고 감사 로그까지 같은
  트랜잭션에서 커밋한다.
- **`document_versions.uploaded_by_display_name` 은 스냅샷.** 사용자가 개명해도 과거 업로더
  표기가 그대로 남는다. Login ID 와 표시 이름을 함께 저장하고, 표시 이름은 업로드 당시 값을
  스냅샷으로 보존한다.
- **`role` 은 PG enum 이 아닌 varchar.** 향후 `viewer` / `editor` / `manager` 추가 시 타입
  재작성 마이그레이션이 필요 없다.
- **대소문자 무시 유니크는 `lower(...)` 함수 인덱스.** 애플리케이션 비교와 DB 제약이 일치한다.
- **`stored_files` 가 물리 저장을 추상화.** `storage_backend` + `storage_key` 로 분리해
  두었으므로, NAS / S3 / MinIO 전환 시 `app/storage.py` 에 클래스를 추가하고 팩토리 한 줄만
  바꾸면 된다.
- **업로드마다 물리 파일을 새로 쓴다.** 내용이 같아도 중복 제거하지 않는다. 각 버전이 자기
  파일을 소유하므로 한 버전의 보관/복원이 다른 버전에 영향을 주지 않는다. SHA-256 은 경고와
  무결성 검증에만 쓴다.
- **`audit_logs` 는 append-only.** 애플리케이션에 UPDATE / DELETE 경로가 아예 없다.

## Archive(Soft delete) 규칙
<!-- akela: id=manual-hub-archive-rules scope=manual-hub tier=must -->

- 문서 / 버전 모두 Archive(Soft delete)와 Restore 만 있고 Hard delete 는 없다.
- **Current 버전은 보관할 수 없다.** 먼저 다른 버전을 Current 로 지정해야 한다 — 문서에
  최신본이 없는 상태가 되지 않게 하려는 장치.
- 문서를 보관하면 새 버전을 올릴 수 없다 — 먼저 복원해야 한다.
- 보관해도 기존 버전 파일은 그대로 다운로드할 수 있다.
- 문서 분류(Category)도 삭제할 수 없다. 그 분류를 사용하는 활성 문서가 있으면 비활성화가
  거부된다.
- 제품도 삭제할 수 없다. 문서가 참조하고 있기 때문이다. 비활성화만 가능하며, 기존 문서와
  파일은 삭제되지 않는다.

## 정렬 규칙
<!-- akela: id=manual-hub-sort-rules scope=manual-hub tier=should -->

- 개정 번호는 자연 정렬 (`V1.0.9` < `V1.0.10`, 문자열 그대로 비교하지 않음).
- 사람 이름은 한글 가나다순.
- 빈 값은 오름차순·내림차순 모두 항상 마지막.
- 문서 분류는 알파벳이 아니라 관리자가 지정한 표시 순서를 따른다.
- Documents 목록의 기본 정렬은 제품 기준.

## 파일 저장 규칙
<!-- akela: id=manual-hub-file-storage-rules scope=manual-hub tier=must -->

- 중앙 저장, UUID 기반 경로: `<DATA_ROOT>/storage/<product-uuid>/<document-uuid>/<version-uuid>/<file-uuid>.<ext>`.
  원본 파일명은 파일시스템에 쓰지 않고 DB(`stored_files.original_file_name`)에만 메타데이터로
  보관한다 — path traversal 및 파일명 인코딩 문제를 구조적으로 제거하기 위함.
- SHA-256 계산 → 동일 내용 파일 업로드 시 경고(차단하지 않음).
- 확장자 허용 목록 + 매직 넘버 검사 + 크기 제한 + 실행 권한 없이 저장.
