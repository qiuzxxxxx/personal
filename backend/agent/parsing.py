"""Server-side extraction of text from uploaded documents.

Images are kept intact and later encoded as data URLs for multimodal models.
"""
from __future__ import annotations

import io
import mimetypes
from pathlib import Path
from zipfile import ZipFile

try:  # PyMuPDF >= 1.24 ships the modern `pymupdf` module name
    import pymupdf as fitz
except ImportError:  # pragma: no cover - older PyMuPDF releases
    import fitz  # type: ignore[no-redef]
from docx import Document
from PIL import Image, UnidentifiedImageError

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_CHARS = 80_000
MAX_DOCX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_DOCX_ENTRIES = 5000
MAX_PDF_PAGES = 200
MAX_IMAGE_PIXELS = 16_000_000

DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_EXTENSIONS = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class AttachmentError(ValueError):
    """Raised for an upload that cannot be safely accepted."""


def extension_of(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def is_image_upload(filename: str, mime_type: str = "") -> bool:
    return extension_of(filename) in IMAGE_EXTENSIONS or mime_type.startswith("image/")


def mime_for(filename: str, supplied: str = "") -> str:
    ext = extension_of(filename)
    if ext in IMAGE_MIME_TYPES:
        return IMAGE_MIME_TYPES[ext]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or supplied or "application/octet-stream"


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "big5"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_pdf(raw: bytes) -> str:
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean validation error
        raise AttachmentError("PDF 文件无法读取，可能已经损坏或被加密。") from exc

    try:
        if document.needs_pass:
            raise AttachmentError("该 PDF 已加密，暂不支持解析。")
        pages: list[str] = []
        for index, page in enumerate(document):
            if index >= MAX_PDF_PAGES:
                break
            text = page.get_text("text").strip()
            if text:
                pages.append(f"--- 第 {index + 1} 页 ---\n{text}")
            if sum(len(item) for item in pages) >= MAX_EXTRACTED_CHARS:
                break
        return "\n\n".join(pages).strip()
    finally:
        document.close()


def _measure_expanded_size(archive: ZipFile) -> int:
    """Count the bytes a zip really expands to.

    The central directory of a zip can lie about the uncompressed size, so
    the declared value is only a hint.  The members are read and counted with
    a hard limit, which keeps the memory of a zip bomb bounded.
    """
    total = 0
    entries = 0
    for item in archive.infolist():
        entries += 1
        if entries > MAX_DOCX_ENTRIES:
            raise AttachmentError("文档条目过多，已停止解析。")
        if item.file_size > MAX_DOCX_EXPANDED_BYTES:
            raise AttachmentError("DOCX 解压后过大，请缩小文档后重试。")
        with archive.open(item) as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOCX_EXPANDED_BYTES:
                    raise AttachmentError("DOCX 解压后过大，请缩小文档后重试。")
    return total


def _extract_docx(raw: bytes) -> str:
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            _measure_expanded_size(archive)
        document = Document(io.BytesIO(raw))
    except AttachmentError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AttachmentError("Word 文件无法读取，请确认它是有效的 .docx 文件。") from exc

    blocks: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            style = (paragraph.style.name or "").lower() if paragraph.style else ""
            if "heading" in style:
                blocks.append(f"## {text}")
            else:
                blocks.append(text)
    for table_index, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(f"[表格 {table_index}]\n" + "\n".join(rows))
    return "\n\n".join(blocks).strip()


def _validate_image(raw: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise AttachmentError("图片像素过多，请缩小图片后重试。")
            image.verify()
    except AttachmentError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise AttachmentError("图片文件无法识别，请上传有效的 PNG / JPG / WebP 图片。") from exc
    if width <= 0 or height <= 0:
        raise AttachmentError("图片尺寸无效。")
    return width, height


def parse_attachment(filename: str, mime_type: str, raw: bytes) -> dict:
    """Validate an upload and return metadata + extracted text.

    Raises AttachmentError with a human-readable Chinese message on failure.
    """
    name = Path(filename or "file").name
    ext = extension_of(name)
    if ext not in ALLOWED_EXTENSIONS:
        raise AttachmentError("暂不支持该文件类型，可上传 PDF、DOCX、TXT、MD 或图片。")
    if not raw:
        raise AttachmentError("不能上传空文件。")
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise AttachmentError("文件超过 25 MB，请压缩后重试。")

    detected_mime = mime_for(name, mime_type)
    image = ext in IMAGE_EXTENSIONS
    extracted_text = ""

    if image:
        _validate_image(raw)
    elif ext == ".pdf":
        extracted_text = _extract_pdf(raw)
    elif ext == ".docx":
        extracted_text = _extract_docx(raw)
    else:
        extracted_text = _decode_text(raw).strip()

    if not image and not extracted_text:
        extracted_text = "（该文档未检测到可提取的文字内容。）"

    return {
        "original_name": name[:255],
        "mime_type": detected_mime,
        "file_size": len(raw),
        "is_image": image,
        "extracted_text": extracted_text[:MAX_EXTRACTED_CHARS],
    }
