"""Private material library helpers: validation, storage and integrity."""
from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path

from django.conf import settings

MAX_MATERIAL_BYTES = 1024 * 1024 * 1024
MAX_NAME_LENGTH = 255

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".log", ".json", ".xml"}
OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz"}
MEDIA_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".mp4", ".mov", ".webm", ".mkv"}
PDF_EXTENSIONS = {".pdf"}
DOWNLOAD_ONLY_EXTENSIONS = {".svg", ".html", ".htm"}

ALLOWED_EXTENSIONS = (
    IMAGE_EXTENSIONS
    | TEXT_EXTENSIONS
    | OFFICE_EXTENSIONS
    | ARCHIVE_EXTENSIONS
    | MEDIA_EXTENSIONS
    | PDF_EXTENSIONS
    | DOWNLOAD_ONLY_EXTENSIONS
)

PREVIEWABLE_EXTENSIONS = (
    IMAGE_EXTENSIONS | TEXT_EXTENSIONS | PDF_EXTENSIONS | {".md", ".markdown"}
)

EXTENSION_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".log": "text/plain",
    ".json": "application/json",
    ".xml": "application/xml",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".svg": "image/svg+xml",
    ".html": "text/html",
    ".htm": "text/html",
}

# Container formats that share the same signature.  A file whose sniffed type
# and whose extension both belong to this family is accepted, which covers
# legacy Office documents and the OOXML (.docx/.xlsx/.pptx) zip containers.
OFFICE_FAMILY = {
    "application/zip",
    "application/vnd.ms-office",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class MaterialError(ValueError):
    """Raised when a file is not acceptable for the private library."""

    def __init__(self, detail: str, code: str = "invalid_file"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


def safe_original_name(raw: str) -> str:
    name = Path(str(raw or "").replace("\\", "/")).name.strip().replace("\x00", "")
    if not name:
        return "未命名文件"
    return name[:MAX_NAME_LENGTH]


def extension_of(name: str) -> str:
    return Path(name).suffix.lower()


def guess_mime(name: str) -> str:
    explicit = EXTENSION_MIME.get(extension_of(name))
    if explicit:
        return explicit
    guessed = mimetypes.guess_type(name)[0]
    return guessed or "application/octet-stream"


def is_previewable(name: str) -> bool:
    return extension_of(name) in PREVIEWABLE_EXTENSIONS


def _looks_like_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        # A truncated multi-byte sequence at the boundary is acceptable.
        try:
            head[:-4].decode("utf-8")
        except UnicodeDecodeError:
            return False
    printable = sum(1 for byte in head if 32 <= byte <= 126 or byte in (9, 10, 13) or byte >= 128)
    return bool(head) and printable / len(head) > 0.85


def sniff_content(head: bytes) -> str | None:
    """Return the detected mime type of the file header, or None when unknown."""
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"BM"):
        return "image/bmp"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/vnd.ms-office"
    if head.startswith(b"ID3") or head[:2] == b"\xff\xfb":
        return "audio/mpeg"
    if len(head) > 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    if head.startswith(b"\x1f\x8b"):
        return "application/gzip"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "application/x-7z-compressed"
    if _looks_like_text(head):
        return "text/plain"
    return None


def validate_extension(name: str) -> str:
    suffix = extension_of(name)
    if not suffix:
        raise MaterialError("文件缺少扩展名，无法安全保存。")
    if suffix not in ALLOWED_EXTENSIONS:
        raise MaterialError(f"暂不支持 {suffix} 类型的文件。")
    return suffix


def validate_upload(upload) -> tuple[str, str]:
    """Validate an uploaded file and return (suffix, detected mime)."""
    name = safe_original_name(upload.name)
    suffix = validate_extension(name)
    if upload.size <= 0:
        raise MaterialError("不能上传空文件。")
    if upload.size > MAX_MATERIAL_BYTES:
        raise MaterialError(
            "文件超过 1 GB 限制。", code="file_too_large"
        )
    head = upload.read(4096)
    try:
        upload.seek(0)
    except (AttributeError, ValueError):  # pragma: no cover - defensive
        pass
    detected = sniff_content(head)
    if detected is None:
        raise MaterialError("文件内容无法识别，已拒绝保存。")
    expected = EXTENSION_MIME.get(suffix)
    if expected and detected != expected:
        # Office formats share container signatures; allow those families.
        # OOXML files (.docx/.xlsx/.pptx) are zip containers, so the sniffed
        # type is "application/zip" while the extension maps to the specific
        # openxmlformats mime.
        if not (detected in OFFICE_FAMILY and expected in OFFICE_FAMILY):
            raise MaterialError("文件内容与扩展名不一致，已拒绝保存。")
    return suffix, detected


def storage_name(suffix: str) -> str:
    """Server generated storage name; the original name is never used on disk."""
    return f"{uuid.uuid4().hex}{suffix}"


def sha256_of(file_obj) -> str:
    digest = hashlib.sha256()
    for chunk in file_obj.chunks(4096):
        digest.update(chunk)
    return digest.hexdigest()


def library_storage_root() -> Path:
    return Path(settings.MEDIA_ROOT) / "library"
