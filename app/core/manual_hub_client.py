"""하위 서비스인 매뉴얼 서버(services/qa-manual-hub)의 HTTP API 클라이언트.

두 시스템은 프로세스도 DB도 공유하지 않는 별도 배포 단위다. 그 경계를 지키기 위해 이
모듈은 **HTTP API만 사용한다** — 매뉴얼 서버의 코드를 import 하거나 PostgreSQL·문서
저장소를 직접 읽지 않는다.

설정이 없으면 아무 일도 하지 않는다(`from_settings()`가 `None`). 매뉴얼 서버를 배포하지
않은 환경이나 자격증명을 넣지 않은 환경에서도 핵심 앱은 그대로 동작해야 하기 때문이다.
같은 이유로 조회 실패는 예외를 밖으로 던지지 않고 빈 결과로 처리한다 — 매뉴얼 서버가
내려가도 회귀 분석과 매뉴얼 개정 검증은 계속 돌아가야 한다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class HubDocument:
    """매뉴얼 서버에 등록된 문서 하나와 그 Current 버전."""

    document_id: str
    name: str
    category: str
    current_revision: str
    current_version_label: str
    current_version_id: str | None

    def describe_current(self) -> str:
        """대조 결과에 표시할 Current 식별자.

        매뉴얼 서버는 Revision/Version 형식을 강제하지 않고 둘 다 비워 둘 수도 있다
        (문서에 적힌 그대로 입력하는 정책). 그래서 있는 것을 순서대로 쓰고, 둘 다
        없으면 출처만 밝힌다."""
        for value in (self.current_revision, self.current_version_label):
            if value.strip():
                return f"매뉴얼 서버 {value.strip()}"
        return "매뉴얼 서버"


def _filename_from_disposition(header: str | None, fallback: str) -> str:
    """RFC 6266 Content-Disposition 에서 파일명을 뽑는다.

    매뉴얼 서버는 한글 파일명을 `filename*=UTF-8''...` 로 보낸다. 확장자를 살려야
    다운로드한 파일을 파서가 형식별로 처리할 수 있다."""
    if not header:
        return fallback
    match = re.search(r"filename\*=UTF-8''([^;]+)", header, re.IGNORECASE)
    if match:
        return unquote(match.group(1).strip())
    match = re.search(r'filename="([^"]+)"', header, re.IGNORECASE)
    if match:
        return match.group(1)
    return fallback


class ManualHubClient:
    """세션 쿠키 기반 클라이언트. `with` 블록 안에서만 로그인 상태를 유지한다."""

    def __init__(self, base_url: str, login_id: str, password: str,
                 client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._login_id = login_id
        self._password = password
        # 테스트는 httpx.MockTransport 를 담은 client 를 주입한다 (Gemini 클라이언트와 같은 방식).
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
        self._owns_client = client is None
        self._logged_in = False

    # --- 수명주기 ---------------------------------------------------------- #

    def __enter__(self) -> ManualHubClient:
        self.login()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # --- 저수준 ------------------------------------------------------------ #

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def login(self) -> bool:
        """실패해도 예외를 던지지 않는다. 성공 여부만 돌려준다."""
        if self._logged_in:
            return True
        try:
            response = self._client.post(
                self._url("/auth/login"),
                json={"login_id": self._login_id, "password": self._password},
            )
        except httpx.HTTPError as exc:
            logger.warning("매뉴얼 서버 로그인 실패 (연결): %s", type(exc).__name__)
            return False
        if response.status_code != 200:
            # 비밀번호를 로그에 남기지 않기 위해 상태 코드만 기록한다.
            logger.warning("매뉴얼 서버 로그인 실패: HTTP %s", response.status_code)
            return False
        self._logged_in = True
        return True

    def _get_json(self, path: str, params: dict | None = None):
        try:
            response = self._client.get(self._url(path), params=params)
            if response.status_code != 200:
                logger.warning("매뉴얼 서버 조회 실패 %s: HTTP %s", path, response.status_code)
                return None
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("매뉴얼 서버 조회 실패 %s: %s", path, type(exc).__name__)
            return None

    # --- 조회 -------------------------------------------------------------- #

    def find_product_id(self, product_name: str) -> str | None:
        """제품 이름으로 매뉴얼 서버의 제품 id 를 찾는다 (대소문자 무시)."""
        rows = self._get_json("/products") or []
        target = product_name.strip().lower()
        for row in rows:
            if str(row.get("name", "")).strip().lower() == target:
                return str(row.get("id"))
        # 이름이 정확히 같지 않으면 코드로도 시도한다.
        for row in rows:
            if str(row.get("code") or "").strip().lower() == target:
                return str(row.get("id"))
        return None

    def documents(self, product_id: str) -> list[HubDocument]:
        """제품의 활성 문서 목록. Current 버전이 없는 문서는 제외한다."""
        rows = self._get_json("/documents", params={"product_id": product_id}) or []
        result: list[HubDocument] = []
        for row in rows:
            version_id = row.get("current_version_id")
            if not version_id:
                continue
            result.append(HubDocument(
                document_id=str(row.get("id")),
                name=str(row.get("name", "")),
                category=str(row.get("category_name") or row.get("category") or ""),
                current_revision=str(row.get("current_revision") or ""),
                current_version_label=str(row.get("current_version_label") or ""),
                current_version_id=str(version_id),
            ))
        return result

    def download_current(self, document: HubDocument, destination_dir: Path) -> Path | None:
        """Current 버전 파일을 내려받아 저장한 경로를 돌려준다. 실패하면 None.

        같은 버전을 이미 받아 뒀으면 다시 내려받지 않는다. 실제 매뉴얼은 한 건이 수십 MB라
        검증할 때마다 전부 다시 받으면 느리고 서버에도 부담이다. 파일명에 version id 가
        들어가므로 Current 가 바뀌면 자동으로 새로 받는다."""
        cached = self._cached_path(document, destination_dir)
        if cached is not None:
            return cached
        try:
            response = self._client.get(
                self._url(f"/documents/{document.document_id}/current/download"))
            if response.status_code != 200:
                logger.warning("매뉴얼 서버 다운로드 실패 %s: HTTP %s",
                               document.name, response.status_code)
                return None
            content = response.content
        except httpx.HTTPError as exc:
            logger.warning("매뉴얼 서버 다운로드 실패 %s: %s", document.name, type(exc).__name__)
            return None

        filename = _filename_from_disposition(
            response.headers.get("content-disposition"), f"{document.document_id}.bin")
        # 서버가 준 파일명을 그대로 경로에 쓰지 않는다 — 디렉터리 이탈을 막기 위해
        # 이름 부분만 취하고 문서·버전 id 를 접두어로 붙여 충돌과 버전 혼동을 막는다.
        safe_name = Path(filename).name or f"{document.document_id}.bin"
        destination_dir.mkdir(parents=True, exist_ok=True)
        path = destination_dir / f"{self._cache_prefix(document)}{safe_name}"
        path.write_bytes(content)
        self._prune_old_versions(document, destination_dir, keep=path)
        return path

    # --- 로컬 사본 관리 ------------------------------------------------------ #

    @staticmethod
    def _cache_prefix(document: HubDocument) -> str:
        return f"{document.document_id}_{document.current_version_id}_"

    def _cached_path(self, document: HubDocument, destination_dir: Path) -> Path | None:
        prefix = self._cache_prefix(document)
        if not destination_dir.exists():
            return None
        for candidate in destination_dir.glob(f"{prefix}*"):
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate
        return None

    def _prune_old_versions(self, document: HubDocument, destination_dir: Path, keep: Path) -> None:
        """같은 문서의 지난 버전 사본을 지운다. 대조용 사본이라 이력을 남길 이유가 없다."""
        for candidate in destination_dir.glob(f"{document.document_id}_*"):
            if candidate.is_file() and candidate != keep:
                try:
                    candidate.unlink()
                except OSError:
                    logger.debug("이전 버전 사본 삭제 실패: %s", candidate.name)


def from_settings(settings: Settings | None = None,
                  client: httpx.Client | None = None) -> ManualHubClient | None:
    """설정과 자격증명이 모두 있을 때만 클라이언트를 만든다. 없으면 None."""
    settings = settings or get_settings()
    api_url = str(settings.get("services.manual_hub.api_url") or "").strip()
    login_id = getattr(settings.secrets, "manual_hub_user", "")
    password = getattr(settings.secrets, "manual_hub_password", "")
    if not (api_url and login_id and password):
        return None
    return ManualHubClient(api_url, login_id, password, client=client)
