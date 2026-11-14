"""Knowledge ingestion: documents, revisions, chunking and index jobs.

Importing a source creates the document, a revision and a persistent index
job inside one transaction. The worker then parses outside the transaction and
switches the index over atomically.
"""
from __future__ import annotations

import hashlib
import uuid

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeRevision,
)

PIPELINE_VERSION = "v1"
CHUNK_TARGET_CHARS = 600
CHUNK_MIN_CHARS = 200
CHUNK_OVERLAP_CHARS = 80
CHUNK_WRITE_BATCH = 200
MAX_CHUNKS_PER_OWNER = 10_000


class IngestionError(ValueError):
    def __init__(self, detail: str, code: str = "invalid_payload"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for CJK and latin text."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk * 1.0 + other / 3.5) + 1


def chunk_segments(segments) -> list[dict]:
    """Group parsed segments into overlapping chunks.

    Every effective source character must end up in at least one chunk: the
    tail of a long paragraph is kept even when it is shorter than the
    minimum size, otherwise the end of a document would be unsearchable.
    Neighbouring chunks share a real overlap so a query whose terms sit on
    a chunk boundary still matches.
    """
    chunks: list[dict] = []
    buffer: list[str] = []
    buffer_len = 0
    heading = ""
    page_start: int | None = None
    page_end: int | None = None
    char_start = 0
    char_end = 0
    # Text carried from the previous chunk so the next one starts with it.
    overlap_text = ""
    overlap_from = 0

    def flush(keep_overlap: bool = False) -> None:
        """Emit the buffered text; optionally carry its tail to the next chunk."""
        nonlocal buffer, buffer_len, overlap_text, overlap_from
        body = "\n".join(buffer).strip()
        if body:
            chunks.append(
                {
                    "text": body,
                    "heading_path": heading,
                    "page_start": page_start,
                    "page_end": page_end,
                    "char_start": char_start,
                    "char_end": char_end,
                }
            )
            if keep_overlap and len(body) > CHUNK_OVERLAP_CHARS:
                overlap_text = body[-CHUNK_OVERLAP_CHARS:]
                overlap_from = max(char_end - len(overlap_text), 0)
            else:
                overlap_text = ""
        buffer = []
        buffer_len = 0

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if len(text) > CHUNK_TARGET_CHARS:
            # A single oversized paragraph is cut on its own. The walk below
            # always ends exactly at the end of the paragraph, and a trailing
            # piece shorter than the minimum size is merged into the previous
            # chunk instead of being dropped.
            flush()
            cuts: list[tuple[int, int]] = []
            start = 0
            while start < len(text):
                end = min(start + CHUNK_TARGET_CHARS, len(text))
                cuts.append((start, end))
                if end >= len(text):
                    break
                start = end - CHUNK_OVERLAP_CHARS
            emitted_end = 0
            for index, (cut_start, cut_end) in enumerate(cuts):
                body = text[cut_start:cut_end].strip()
                if not body:
                    continue
                if index == len(cuts) - 1 and len(body) < CHUNK_MIN_CHARS and chunks:
                    # Merge only the part that the previous chunk does not
                    # already contain, so no character is duplicated or lost.
                    previous = chunks[-1]
                    tail = text[emitted_end:]
                    if tail.strip():
                        previous["text"] = f"{previous['text']}\n{tail.strip()}"
                    previous["char_end"] = segment.char_start + len(text)
                    emitted_end = len(text)
                    break
                chunks.append(
                    {
                        "text": body,
                        "heading_path": segment.heading_path,
                        "page_start": segment.page_start,
                        "page_end": segment.page_end,
                        "char_start": segment.char_start + cut_start,
                        "char_end": segment.char_start + cut_end,
                    }
                )
                emitted_end = cut_end
            # The next chunk starts with the tail of the last one.
            if chunks:
                last_text = chunks[-1]["text"]
                if len(last_text) > CHUNK_OVERLAP_CHARS:
                    overlap_text = last_text[-CHUNK_OVERLAP_CHARS:]
                    overlap_from = chunks[-1]["char_end"] - len(overlap_text)
            continue
        if buffer_len and buffer_len + len(text) > CHUNK_TARGET_CHARS:
            flush(keep_overlap=True)
        if not buffer:
            # Start a new chunk; the overlap tail becomes its first part.
            heading = segment.heading_path
            page_start = segment.page_start
            page_end = segment.page_end
            char_start = overlap_from if overlap_text else segment.char_start
            if overlap_text:
                buffer.append(overlap_text)
                buffer_len = len(overlap_text)
            overlap_text = ""
        buffer.append(text)
        buffer_len += len(text) + 1
        char_end = segment.char_end
        if buffer_len >= CHUNK_TARGET_CHARS:
            flush(keep_overlap=True)
    flush()
    return chunks


def next_revision_no(document: KnowledgeDocument) -> int:
    latest = KnowledgeRevision.objects.filter(document=document).aggregate(
        value=Max("revision_no")
    )
    return int(latest["value"] or 0) + 1


@transaction.atomic
def create_document(
    *,
    owner,
    title: str,
    collection=None,
    source_type: str = "manual",
    manual_body: str = "",
    content_origin: str = "user_authored",
    ai_enabled: bool = False,
    source_material=None,
    source_entry=None,
    source_message=None,
    source_version: int = 1,
    source_title: str = "",
    source_date=None,
) -> KnowledgeDocument:
    document = KnowledgeDocument.objects.create(
        owner=owner,
        collection=collection,
        title=title[:200],
        source_type=source_type,
        manual_body=manual_body,
        content_origin=content_origin,
        ai_enabled=bool(ai_enabled),
        source_material=source_material,
        source_entry=source_entry,
        source_message=source_message,
        source_version=source_version,
        source_title=source_title[:300],
        source_date=source_date,
    )
    revision = KnowledgeRevision.objects.create(
        document=document,
        revision_no=1,
        source_version=source_version,
        source_hash=content_hash(manual_body),
        index_status="pending",
    )
    document.current_revision = revision
    document.save(update_fields=["current_revision"])
    enqueue_job(document, revision)
    return document


@transaction.atomic
def enqueue_job(document: KnowledgeDocument, revision: KnowledgeRevision) -> KnowledgeIndexJob:
    job, created = KnowledgeIndexJob.objects.get_or_create(
        document=document,
        revision=revision,
        pipeline_version=PIPELINE_VERSION,
        defaults={
            "owner": document.owner,
            "status": "pending",
            "next_run_at": timezone.now(),
        },
    )
    if not created and job.status in {"done", "failed"}:
        job.status = "pending"
        job.next_run_at = timezone.now()
        job.save(update_fields=["status", "next_run_at", "updated_at"])
    return job


@transaction.atomic
def replace_chunks(document: KnowledgeDocument, revision: KnowledgeRevision, chunks: list[dict]) -> int:
    owner = document.owner
    existing = KnowledgeChunk.objects.filter(owner=owner).count()
    if existing + len(chunks) > MAX_CHUNKS_PER_OWNER:
        raise IngestionError(
            f"分段数量超过每账号 {MAX_CHUNKS_PER_OWNER} 的上限。", code="quota_exceeded"
        )
    KnowledgeChunk.objects.filter(revision=revision).delete()
    # Section 12.7: write in batches so a large document never creates one
    # huge statement.
    for start in range(0, len(chunks), CHUNK_WRITE_BATCH):
        batch = chunks[start : start + CHUNK_WRITE_BATCH]
        KnowledgeChunk.objects.bulk_create(
            [
                KnowledgeChunk(
                    owner=owner,
                    document=document,
                    revision=revision,
                    ordinal=start + index,
                    text=item["text"],
                    content_hash=content_hash(item["text"]),
                    heading_path=item["heading_path"][:300],
                    page_start=item["page_start"],
                    page_end=item["page_end"],
                    char_start=item["char_start"],
                    char_end=item["char_end"],
                    token_estimate=estimate_tokens(item["text"]),
                )
                for index, item in enumerate(batch)
            ]
        )
    return len(chunks)


def new_claim_token() -> str:
    return uuid.uuid4().hex
