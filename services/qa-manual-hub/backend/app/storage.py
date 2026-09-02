"""Storage abstraction.

Business logic only ever talks to a ``StorageBackend``.  Today the only
implementation writes to a local directory; swapping in NAS / S3 / MinIO later
means adding a class here and changing one factory line -- no router or service
code changes.

Layout (spec section 19)::

    <storage_root>/<product_id>/<document_id>/<version_id>/<file_id>.<ext>

The original file name never touches the filesystem, which removes path
traversal and encoding problems by construction.  It lives in
``stored_files.original_file_name`` instead.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from .config import settings

CHUNK_SIZE = 1024 * 1024  # 1 MiB

# Extensions are validated against an allow-list, then additionally forced
# through this pattern so a crafted value can never influence the path.
_SAFE_EXT_RE = re.compile(r"^[A-Za-z0-9]{1,16}$")

# Magic-number prefixes for the formats worth checking.  Office 2007+ files and
# any other zip container share the PK signature, which is why docx/xlsx/pptx
# map to the same bytes.
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "ppt": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}

MIME_BY_EXT = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

# Rendered inline in the browser as-is; everything else is sent as an attachment.
DIRECT_PREVIEW_EXT = {"pdf", "png", "jpg", "jpeg", "txt", "md"}

# Rendered inline too, but only after conversion to PDF via LibreOffice --
# see ``convert_to_pdf`` / ``LocalDiskStorage.ensure_preview_pdf``.
OFFICE_PREVIEW_EXT = {"doc", "docx", "ppt", "pptx", "xls", "xlsx"}


class StorageError(RuntimeError):
    pass


class FileTooLargeError(StorageError):
    pass


class ExtensionNotAllowedError(StorageError):
    pass


class ContentTypeMismatchError(StorageError):
    pass


class ConversionError(StorageError):
    """Office document could not be turned into a previewable PDF."""


# uvicorn runs this app as multiple worker PROCESSES (see the systemd unit),
# so an in-memory lock only protects against races within one worker -- two
# people opening the same not-yet-cached document at once can still land on
# different workers. A plain lock *file* is what actually coordinates across
# processes: whichever worker creates it first converts; the rest wait for
# either the cache to appear or the lock to go away (or go stale, if the
# converting worker died).
def _try_acquire_conversion_lock(lock_path: Path) -> bool:
    try:
        os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def _wait_for_conversion(cached: Path, lock_path: Path, timeout: float) -> bool:
    """Poll while another worker converts the same file.

    Returns True once ``cached`` appears. Returns False (caller should try to
    take the lock itself) if the lock disappears without producing a cache,
    or goes stale -- both signs the converting worker died mid-job.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cached.is_file():
            return True
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            return False
        if age > settings.office_preview_timeout_seconds + 30:
            return False
        time.sleep(0.4)
    return False


@dataclass(slots=True)
class SavedFile:
    file_id: uuid.UUID
    storage_key: str
    sha256: str
    byte_size: int
    extension: str
    mime_type: str


def normalise_extension(original_name: str) -> str:
    ext = Path(original_name or "").suffix.lower().lstrip(".")
    if not ext or not _SAFE_EXT_RE.match(ext):
        raise ExtensionNotAllowedError(
            "파일 확장자를 확인할 수 없습니다. 허용된 확장자의 파일을 업로드하세요."
        )
    if ext not in settings.allowed_extension_set:
        allowed = ", ".join(sorted(settings.allowed_extension_set))
        raise ExtensionNotAllowedError(
            f"'{ext}' 확장자는 허용되지 않습니다. 허용 확장자: {allowed}"
        )
    return ext


def check_magic(head: bytes, ext: str) -> None:
    """Verify the declared extension against the file's leading bytes.

    Text-ish formats (txt, md) have no signature, so they are accepted as-is.
    """
    expected = _MAGIC.get(ext)
    if not expected:
        return
    if not any(head.startswith(sig) for sig in expected):
        raise ContentTypeMismatchError(
            f"파일 내용이 '{ext}' 형식과 일치하지 않습니다. 확장자를 확인하세요."
        )


class StorageBackend(Protocol):
    def save(
        self,
        stream: BinaryIO,
        *,
        product_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        original_name: str,
    ) -> SavedFile: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def path(self, storage_key: str) -> Path | None: ...

    def exists(self, storage_key: str) -> bool: ...

    def size(self, storage_key: str) -> int: ...


class LocalDiskStorage:
    """Managed-copy storage on the application server's own disk."""

    backend_name = "local"

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.storage_root)

    # -- internals ------------------------------------------------------- #
    def _resolve(self, storage_key: str) -> Path:
        root = self.root.resolve()
        candidate = (root / storage_key).resolve()
        # Defence in depth: keys are machine-generated, but never trust a path
        # that escapes the storage root.
        if root != candidate and root not in candidate.parents:
            raise StorageError("잘못된 저장 경로입니다.")
        return candidate

    # -- API ------------------------------------------------------------- #
    def save(
        self,
        stream: BinaryIO,
        *,
        product_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        original_name: str,
    ) -> SavedFile:
        ext = normalise_extension(original_name)
        file_id = uuid.uuid4()
        rel_dir = Path(str(product_id)) / str(document_id) / str(version_id)
        rel_key = str((rel_dir / f"{file_id}.{ext}").as_posix())

        target_dir = self._resolve(str(rel_dir))
        target_dir.mkdir(parents=True, exist_ok=True)
        target = self._resolve(rel_key)

        digest = hashlib.sha256()
        total = 0
        head = b""

        # Write to a temp file in the final directory first, then rename.  A
        # crash mid-upload leaves a .part file, never a half-written version.
        fd, tmp_name = tempfile.mkstemp(dir=target_dir, suffix=".part")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = stream.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if not head:
                        head = chunk[:16]
                    total += len(chunk)
                    if total > settings.max_upload_bytes:
                        raise FileTooLargeError(
                            f"파일 크기가 제한({settings.max_upload_mb} MB)을 초과했습니다."
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if total == 0:
                raise StorageError("빈 파일은 업로드할 수 없습니다.")
            check_magic(head, ext)
            # 0o640: readable by the service user and its group, never by others,
            # and never executable.
            os.chmod(tmp_path, 0o640)
            tmp_path.replace(target)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        return SavedFile(
            file_id=file_id,
            storage_key=rel_key,
            sha256=digest.hexdigest(),
            byte_size=total,
            extension=ext,
            mime_type=MIME_BY_EXT.get(ext, "application/octet-stream"),
        )

    def open(self, storage_key: str) -> BinaryIO:
        return self._resolve(storage_key).open("rb")

    def path(self, storage_key: str) -> Path | None:
        return self._resolve(storage_key)

    def exists(self, storage_key: str) -> bool:
        try:
            return self._resolve(storage_key).is_file()
        except StorageError:
            return False

    def size(self, storage_key: str) -> int:
        return self._resolve(storage_key).stat().st_size

    def _preview_cache_path(self, storage_key: str) -> Path:
        source = self._resolve(storage_key)
        return source.parent / f"{source.stem}.preview.pdf"

    def has_cached_preview(self, storage_key: str) -> bool:
        return self._preview_cache_path(storage_key).is_file()

    def ensure_preview_pdf(self, storage_key: str) -> Path:
        """Return a cached PDF rendering of an office file, converting on the
        first request and reusing it afterwards. Versions are immutable once
        uploaded, so the cache never needs to be invalidated.
        """
        source = self._resolve(storage_key)
        cached = self._preview_cache_path(storage_key)
        if cached.is_file():
            return cached

        lock_path = source.parent / f"{source.stem}.preview.lock"
        while not _try_acquire_conversion_lock(lock_path):
            if _wait_for_conversion(
                cached, lock_path, settings.office_preview_timeout_seconds + 20
            ):
                return cached
            # Lock vanished or went stale without a cache showing up --
            # whoever held it is gone. Clear it and try to take over.
            lock_path.unlink(missing_ok=True)

        try:
            if cached.is_file():  # produced by someone else while we waited
                return cached
            # Convert in the OS temp dir, not under source.parent: LibreOffice's
            # per-conversion profile (see convert_to_pdf) writes plenty of its
            # own nested files, and doing that under the storage tree's
            # <product>/<document>/<version>/ UUID chain can walk straight
            # into Windows' 260-char MAX_PATH -- confirmed by hand, it fails
            # silently (exit 0, no PDF, no stderr). Linux has no such limit,
            # but keeping conversion scratch space off the (possibly
            # network-mounted) storage volume is the right call there too.
            with tempfile.TemporaryDirectory() as tmp_dir:
                produced = convert_to_pdf(source, Path(tmp_dir))
                # Copy into a same-directory temp file first, then rename: the
                # copy may cross filesystems (storage_root vs the OS temp dir),
                # but the final rename is atomic and local, so a concurrent
                # request for the same file never sees a half-written cache
                # entry.
                fd, tmp_name = tempfile.mkstemp(dir=source.parent, suffix=".part")
                tmp_cached = Path(tmp_name)
                try:
                    with os.fdopen(fd, "wb") as out, produced.open("rb") as src:
                        shutil.copyfileobj(src, out)
                    os.chmod(tmp_cached, 0o640)
                    tmp_cached.replace(cached)
                except BaseException:
                    tmp_cached.unlink(missing_ok=True)
                    raise
        finally:
            lock_path.unlink(missing_ok=True)
        return cached

    def discard(self, storage_key: str) -> None:
        """Remove a just-written file after the surrounding transaction failed.

        This is the only delete path in the system and it only ever runs on a
        file whose database row was never committed.
        """
        try:
            p = self._resolve(storage_key)
        except StorageError:
            return
        p.unlink(missing_ok=True)
        # Clean up the now-empty version directory, but stop there.
        try:
            p.parent.rmdir()
        except OSError:
            pass


_backend: LocalDiskStorage | None = None


def get_storage() -> LocalDiskStorage:
    global _backend
    if _backend is None:
        _backend = LocalDiskStorage()
    return _backend


def office_preview_available() -> bool:
    """Whether this host can convert office documents to PDF right now.

    Checked live (not cached) so installing LibreOffice on a running server
    takes effect without a restart -- ``shutil.which`` is a cheap stat, not
    worth caching stale.
    """
    return shutil.which(settings.office_preview_binary) is not None


def needs_conversion(ext: str) -> bool:
    return ext.lower().lstrip(".") in OFFICE_PREVIEW_EXT


def is_inline_previewable(ext: str) -> bool:
    ext = ext.lower().lstrip(".")
    if ext in DIRECT_PREVIEW_EXT:
        return True
    if ext in OFFICE_PREVIEW_EXT:
        return office_preview_available()
    return False


def convert_to_pdf(source: Path, out_dir: Path) -> Path:
    """Render ``source`` (doc/docx/xls/xlsx/ppt/pptx) to a PDF in ``out_dir``
    via headless LibreOffice, and return the produced file's path.
    """
    binary = settings.office_preview_binary
    if shutil.which(binary) is None:
        raise ConversionError(
            "서버에 LibreOffice(soffice)가 설치되어 있지 않아 미리보기를 만들 수 없습니다. "
            "다운로드 후 확인하세요."
        )
    # LibreOffice headless shares one profile per user by default, which two
    # concurrent conversions will corrupt/deadlock over. -env:UserInstallation
    # points each invocation at its own throwaway profile inside out_dir
    # (itself a fresh temp directory per call), so requests never collide.
    # Path.as_uri() (not a hand-built "file://" + as_posix()) is what makes
    # this correct on Windows too, where a bare as_posix() omits the leading
    # slash the file:// scheme needs (verified against a real soffice.exe).
    profile_dir = out_dir / "lo-profile"
    try:
        result = subprocess.run(
            [
                binary,
                "--headless",
                "--norestore",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(source),
            ],
            capture_output=True,
            timeout=settings.office_preview_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(
            "문서를 PDF로 변환하는 데 시간이 너무 오래 걸립니다. 다운로드 후 확인하세요."
        ) from exc

    produced = out_dir / f"{source.stem}.pdf"
    if result.returncode != 0 or not produced.is_file():
        detail = result.stderr.decode("utf-8", "ignore").strip()[:300]
        raise ConversionError(
            "문서를 PDF로 변환하지 못했습니다. 다운로드 후 확인하세요."
            + (f" ({detail})" if detail else "")
        )
    return produced
