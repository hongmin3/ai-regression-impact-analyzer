# QA Manual Hub — Auth & Permissions

> 이 문서의 저장소 상대 경로(`backend/`, `frontend/`, `deploy/` 등)는 모두
> `services/qa-manual-hub/` 기준이다. `<APP_ROOT>` / `<DATA_ROOT>` 는 서버의
> 런타임 경로이며 저장소 경로가 아니다.


## 비밀번호 해시 및 세션
<!-- akela: id=manual-hub-password-hash-session scope=manual-hub tier=must -->

- **Argon2id** (`argon2-cffi`) 사용. 평문 저장·로깅 없음. 파라미터 상향 시 로그인할 때
  자동 재해싱.
- 길이 정책은 `PASSWORD_MIN_LENGTH` 환경변수 하나로 결정. 기본값 `1` = 사실상 제한 없음
  (빈 값과 앞뒤 공백만 거부). 값을 올리면 API·CLI·웹 폼이 모두 그 값을 따른다.
- 세션은 서버 세션 테이블 + HttpOnly 쿠키. 쿠키에는 256bit 불투명 토큰, DB에는 SHA-256 만
  저장한다.
- 세션 유효 시간은 `SESSION_LIFETIME_HOURS` (기본 8시간). 사용 중이면 자동 연장.
- 로그인하지 않으면 어떤 화면도 볼 수 없다 (프론트엔드 라우팅이 미인증 시 전 경로를 로그인
  화면으로 전환).
- HTTPS 적용 시 `.env` 의 `SESSION_COOKIE_SECURE` 를 `true` 로 바꿔야 한다 (기본 `false`).

## 로그인 실패 메시지 통일
<!-- akela: id=manual-hub-login-failure-message scope=manual-hub tier=must -->

- 없는 ID / 틀린 비밀번호 / 비활성 계정 **모두 동일한 메시지**를 반환한다:
  "아이디 또는 비밀번호가 올바르지 않습니다." 아이디가 틀렸는지 비밀번호가 틀렸는지 알려주지
  않는 것은 보안상 의도된 동작이다. 사유는 서버 로그에만 남긴다.

## 세션 무효화 트리거
<!-- akela: id=manual-hub-session-invalidation scope=manual-hub tier=must -->

다음 이벤트 발생 시 해당 사용자의 열려 있는 모든 세션이 **즉시** revoke 된다.

- 계정 비활성화
- 비밀번호 초기화(관리자에 의한 강제 변경)

비활성화된 계정은 다음 요청에서 바로 튕겨나간다 (열려 있던 탭 포함).

## 역할(Role)과 권한 구조
<!-- akela: id=manual-hub-role-permission-structure scope=manual-hub tier=should -->

- 역할은 `ADMIN` 또는 `USER` 두 종류. `role` 컬럼은 PG enum 이 아닌 varchar 로 저장되어
  향후 `viewer` / `editor` / `manager` 추가 시 타입 재작성 마이그레이션이 불필요하다.
- **일반 User 는 문서 관련 기능 전체 사용 가능** — 문서/버전 등록, 업로드, Set as Current,
  Archive/Restore 등. **사용자 계정 관리만 Admin 으로 제한**된다.
- Admin 전용 기능: 사용자 생성 / 비밀번호 초기화 / 활성·비활성 전환 / 권한 변경, 제품 추가,
  문서 분류 관리.
- 권한 검사는 라우터 의존성(`deps.py` 의 `get_current_user` / `require_admin` 등)으로
  수행된다. 프론트엔드 라우팅과 별개로 API 가 독립적으로 강제한다 — 프론트엔드에서 메뉴를
  숨기는 것만으로 권한 제어를 하지 않는다.

## 구조적으로 차단된 안전장치
<!-- akela: id=manual-hub-safety-guards scope=manual-hub tier=must -->

| 시도 | 결과 | 이유 |
|---|---|---|
| 자기 계정 비활성화 | 거부 | 스스로 잠기는 것 방지 |
| 자기 Admin 권한 해제 | 거부 | 동일. 다른 Admin 에게 요청해야 함 |
| 마지막 활성 Admin 강등·비활성화 | 거부 | 시스템에 Admin 이 하나도 없는 상태 방지 |

이 세 가지는 API 레벨에서 구조적으로 막혀 있으며 우회 경로가 없다. 새 사용자 관리 기능을
추가할 때도 이 제약을 깨지 않아야 한다.

## 모든 Admin 이 잠긴 경우의 복구 경로
<!-- akela: id=manual-hub-admin-lockout-recovery scope=manual-hub tier=should -->

서버 CLI 로만 복구 가능 (웹 UI 경로 없음):

```bash
sudo -u <SERVICE_USER> <APP_ROOT>/scripts/qamh list-users        # 어떤 admin 이 있는지
sudo -u <SERVICE_USER> <APP_ROOT>/scripts/qamh reset-password admin
```

계정이 비활성 상태라면 DB에서 직접 되살려야 한다 (`UPDATE users SET is_active = true ...`).

## 업로더 자동 기록 (권한과 결합된 데이터 무결성 규칙)
<!-- akela: id=manual-hub-uploader-auto-record scope=manual-hub tier=must -->

- 업로더 이름을 사용자가 입력하는 칸이 없다. **지금 로그인한 계정**이 업로더로 자동 기록된다
  (요청 바디로 위조 불가).
- Login ID 와 표시 이름을 함께 저장하고, 표시 이름은 업로드 당시 값을 스냅샷으로 보존한다 →
  사용자가 나중에 개명해도 과거 업로더 표기는 당시 이름 그대로 남는다.
- Login ID 와 표시 이름은 **사용자 스스로 바꿀 수 없다.** 관리자에게 요청해야 하며, Login ID
  를 고정하는 이유는 과거 업로드 기록의 추적성을 지키기 위함이다.

## 감사 로그(Audit Log)와 권한
<!-- akela: id=manual-hub-audit-log-permissions scope=manual-hub tier=must -->

- 25종 이벤트를 append-only 로 기록. 애플리케이션에 UPDATE / DELETE 엔드포인트가 아예 없다.
- 사용자 생성·수정·비밀번호 초기화·활성·비활성·권한 변경 등 계정 관련 이벤트도 모두 감사
  로그 대상.
- Current 버전 변경은 before/after 값을 함께 기록한다.
- 일반 User 도 Audit Log 를 조회할 수 있다 (기록 자체는 누구나 볼 수 있되, 수정/삭제 API가
  없어 무결성이 보장됨).

## 계정 운영 원칙
<!-- akela: id=manual-hub-account-operations scope=manual-hub tier=should -->

- 담당자별 개별 계정을 사용하고 공용 계정을 쓰지 않는다 — 업로더 추적의 근거가 사라지기
  때문이다.
- 초기 비밀번호는 "최초 로그인 시 변경 요구" 를 항상 켜는 것을 권장.
- 퇴사·전출자는 삭제가 아니라 **비활성화**한다 (삭제 기능 자체가 없음 — 문서 이력의
  추적성을 지키기 위한 설계).
