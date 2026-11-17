"""Location-aware text extraction for the knowledge base.

The agent attachment parser truncates text and loses page numbers, so the
knowledge base uses its own extraction that keeps page, heading and character
positions. ``agent.parsing`` stays untouched for the legacy chat attachments.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZipFile

try:  # PyMuPDF >= 1.24 ships the modern `pymupdf` module name
    import pymupdf as fitz
except ImportError:  # pragma: no cover - older PyMuPDF releases
    import fitz  # type: ignore[no-redef]
from docx import Document

MAX_KNOWLEDGE_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 200
MAX_EXTRACTED_CHARS = 500_000
MAX_DOCX_EXPANDED_BYTES = 100 * 1024 * 1024

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".log"}


class KnowledgeParseError(ValueError):
    """Raised when a source document cannot be turned into text."""

    def __init__(self, detail: str, code: str = "parse_failed"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


@dataclass
class Segment:
    """A contiguous piece of the source with its position metadata."""

    text: str
    heading_path: str = ""
    page_start: int | None = None
    page_end: int | None = None
    char_start: int = 0
    char_end: int = 0


@dataclass
class ParseResult:
    segments: list[Segment] = field(default_factory=list)
    text: str = ""
    needs_ocr: bool = False


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "big5"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _markdown_segments(text: str) -> list[Segment]:
    segments: list[Segment] = []
    stack: list[str] = []
    buffer: list[str] = []
    heading = ""
    offset = 0
    start = 0

    def flush() -> None:
        nonlocal buffer, start
        body = "\n".join(buffer).strip()
        if body:
            segments.append(
                Segment(
                    text=body,
                    heading_path=" > ".join(stack),
                    char_start=start,
                    char_end=start + len(body),
                )
            )
        buffer = []

    for line in text.splitlines():
        line_start = offset
        # Every line advances the offset, including headings and blank lines;
        # otherwise the recorded character ranges drift behind the text.
        offset += len(line) + 1
        stripped = line.strip()
        if stripped.startswith("#"):
            flush()
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            while stack and len(stack) >= level:
                stack.pop()
            stack.append(title)
            heading = title
            start = offset
            # The heading itself is searchable content, not only a path.
            segments.append(
                Segment(
                    text=title,
                    heading_path=" > ".join(stack),
                    char_start=line_start,
                    char_end=line_start + len(line),
                )
            )
            continue
        if not stripped:
            flush()
            start = offset
            continue
        if not buffer:
            start = line_start
        buffer.append(line)
    flush()
    return segments


def _plain_segments(text: str) -> list[Segment]:
    segments: list[Segment] = []
    offset = 0
    for block in text.split("\n\n"):
        body = block.strip()
        if not body:
            offset += len(block) + 2
            continue
        segments.append(
            Segment(text=body, char_start=offset, char_end=offset + len(body))
        )
        offset += len(block) + 2
    return segments


def _pdf_segments(raw: bytes) -> tuple[list[Segment], bool]:
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise KnowledgeParseError("PDF 文件无法读取，可能已经损坏或被加密。") from exc
    try:
        if document.needs_pass:
            raise KnowledgeParseError("该 PDF 已加密，暂不支持解析。", code="encrypted_pdf")
        if document.page_count > MAX_PDF_PAGES:
            raise KnowledgeParseError(
                f"PDF 超过 {MAX_PDF_PAGES} 页上限，请拆分后再导入。", code="too_many_pages"
            )
        segments: list[Segment] = []
        total = 0
        empty_pages = 0
        for index, page in enumerate(document):
            text = (page.get_text("text") or "").strip()
            if not text:
                empty_pages += 1
                continue
            segments.append(
                Segment(
                    text=text,
                    heading_path=f"第 {index + 1} 页",
                    page_start=index + 1,
                    page_end=index + 1,
                )
            )
            total += len(text)
            if total >= MAX_EXTRACTED_CHARS:
                raise KnowledgeParseError(
                    f"提取文本超过 {MAX_EXTRACTED_CHARS} 字符上限，请拆分文档。",
                    code="text_too_large",
                )
        needs_ocr = bool(document.page_count) and empty_pages == document.page_count
        return segments, needs_ocr
    finally:
        document.close()


def _docx_segments(raw: bytes) -> list[Segment]:
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_EXPANDED_BYTES:
                raise KnowledgeParseError("DOCX 解压后过大，请缩小文档后重试。")
        document = Document(io.BytesIO(raw))
    except KnowledgeParseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise KnowledgeParseError("Word 文件无法读取，请确认它是有效的 .docx 文件。") from exc

    segments: list[Segment] = []
    stack: list[str] = []
    offset = 0
    for paragraph in document.paragraphs:
        body = paragraph.text.strip()
        if not body:
            offset += len(paragraph.text) + 1
            continue
        style = (paragraph.style.name or "").lower() if paragraph.style else ""
        if "heading" in style:
            level = 1
            digits = "".join(ch for ch in style if ch.isdigit())
            if digits:
                level = max(1, int(digits))
            while stack and len(stack) >= level:
                stack.pop()
            stack.append(body)
            segments.append(
                Segment(
                    text=body,
                    heading_path=" > ".join(stack),
                    char_start=offset,
                    char_end=offset + len(body),
                )
            )
        else:
            segments.append(
                Segment(
                    text=body,
                    heading_path=" > ".join(stack),
                    char_start=offset,
                    char_end=offset + len(body),
                )
            )
        offset += len(paragraph.text) + 1

    for table_index, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            body = "\n".join(rows)
            segments.append(
                Segment(
                    text=body,
                    heading_path=f"表格 {table_index}",
                    char_start=offset,
                    char_end=offset + len(body),
                )
            )
    return segments


def parse_document(filename: str, raw: bytes) -> ParseResult:
    """Extract text with location metadata from a supported source file."""
    if not raw:
        raise KnowledgeParseError("文件内容为空。", code="empty_file")
    if len(raw) > MAX_KNOWLEDGE_BYTES:
        raise KnowledgeParseError(
            "文件超过 25 MB 知识解析上限。", code="file_too_large"
        )
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise KnowledgeParseError(
            "该文件类型暂不支持入库，可使用 TXT、Markdown、PDF 或 DOCX。",
            code="unsupported_type",
        )

    if suffix == ".pdf":
        segments, needs_ocr = _pdf_segments(raw)
        if needs_ocr:
            return ParseResult(segments=[], text="", needs_ocr=True)
    elif suffix == ".docx":
        segments = _docx_segments(raw)
    else:
        text = _decode_text(raw)
        segments = _markdown_segments(text) if suffix in {".md", ".markdown"} else _plain_segments(text)

    total = 0
    for segment in segments:
        total += len(segment.text)
    if total > MAX_EXTRACTED_CHARS:
        raise KnowledgeParseError(
            f"提取文本超过 {MAX_EXTRACTED_CHARS} 字符上限，请拆分文档。",
            code="text_too_large",
        )
    body = "\n\n".join(segment.text for segment in segments)
    return ParseResult(segments=segments, text=body)
