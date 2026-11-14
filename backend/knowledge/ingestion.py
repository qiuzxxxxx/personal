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
    """Group parsed segments into overlapping chunks."""
    chunks: list[dict] = []
    buffer: list[str] = []
    buffer_len = 0
    heading = ""
    page_start: int | None = None
    page_end: int | None = None
    char_start = 0
    char_end = 0

    def flush() -> None:
        nonlocal buffer, buffer_len
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
        buffer = []
        buffer_len = 0

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if buffer_len and buffer_len + len(text) > CHUNK_TARGET_CHARS:
            flush()
            if len(text) > CHUNK_TARGET_CHARS:
                # Long paragraphs are split further with a small overlap.
                step = max(CHUNK_TARGET_CHARS - CHUNK_OVERLAP_CHARS, 1)
                for offset in range(0, len(text), step):
                    piece = text[offset : offset + CHUNK_TARGET_CHARS]
                    if len(piece.strip()) < CHUNK_MIN_CHARS and offset:
                        break
                    chunks.append(
                        {
                            "text": piece.strip(),
                            "heading_path": segment.heading_path,
                            "page_start": segment.page_start,
                            "page_end": segment.page_end,
                            "char_start": segment.char_start + offset,
                            "char_end": segment.char_start + offset + len(piece),
                        }
                    )
                heading = segment.heading_path
                page_start = segment.page_start
                page_end = segment.page_end
                continue
        if not buffer:
            heading = segment.heading_path
            page_start = segment.page_start
            page_end = segment.page_end
            char_start = segment.char_start
        buffer.append(text)
        buffer_len += len(text) + 1
        char_end = segment.char_end
        if buffer_len >= CHUNK_TARGET_CHARS:
            flush()
            # Keep an overlap tail for the next chunk.
            tail = buffer[-1][-CHUNK_OVERLAP_CHARS:] if buffer else ""
            buffer = [tail] if tail else []
            buffer_len = len(tail)
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
    KnowledgeChunk.objects.bulk_create(
        [
            KnowledgeChunk(
                owner=owner,
                document=document,
                revision=revision,
                ordinal=index,
                text=item["text"],
                content_hash=content_hash(item["text"]),
                heading_path=item["heading_path"][:300],
                page_start=item["page_start"],
                page_end=item["page_end"],
                char_start=item["char_start"],
                char_end=item["char_end"],
                token_estimate=estimate_tokens(item["text"]),
            )
            for index, item in enumerate(chunks)
        ]
    )
    return len(chunks)


def new_claim_token() -> str:
    return uuid.uuid4().hex
