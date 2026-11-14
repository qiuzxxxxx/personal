"""Persistent index worker.

Jobs live in the database with a lease and a claim token, so an interrupted
worker never leaves a document half-indexed and a duplicate claim cannot
overwrite a newer result.

Parsing runs in a separate process with a memory limit and a hard timeout
(section 12.7): a pathological document must never exhaust the worker.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from workspace.models import DailyEntry, Material

from .ingestion import chunk_segments, content_hash, enqueue_job, replace_chunks
from .models import KnowledgeChunk, KnowledgeDocument, KnowledgeIndexJob, KnowledgeRevision
from .parsing import KnowledgeParseError, Segment

logger = logging.getLogger(__name__)

JOB_LEASE_SECONDS = 120
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 60
# Section 12.7: the parse subprocess may not use more than 450 MiB and must
# finish within 120 seconds.
PARSE_MEMORY_LIMIT_BYTES = 450 * 1024 * 1024
PARSE_TIMEOUT_SECONDS = 120


def claim_next_job(lease_seconds: int = JOB_LEASE_SECONDS):
    """Atomically claim one due job; returns ``(job, claim_token)`` or None.

    Jobs whose lease is still held by another worker are skipped instead of
    blocking the whole queue.
    """
    now = timezone.now()
    with transaction.atomic():
        candidates = list(
            KnowledgeIndexJob.objects.select_for_update()
            .filter(status__in=["pending", "processing"])
            .filter(next_run_at__lte=now)
            .order_by("created_at")[:50]
        )
        for job in candidates:
            if (
                job.status == "processing"
                and job.lease_until
                and job.lease_until > now
            ):
                # Another worker still holds the lease; try the next job.
                continue
            claim_token = f"{job.id}-{now.timestamp()}"
            updated = KnowledgeIndexJob.objects.filter(
                pk=job.pk,
                claim_token=job.claim_token,
                status=job.status,
            ).update(
                status="processing",
                claim_token=claim_token,
                lease_until=now + timedelta(seconds=lease_seconds),
                attempts=job.attempts + 1,
                updated_at=now,
            )
            if not updated:
                continue
            job.refresh_from_db()
            return job, claim_token
    return None


def _source_payload(document: KnowledgeDocument) -> tuple[str, dict]:
    """Return (filename, source description) of the document source.

    A file on disk is passed by path so the subprocess never has to hold the
    whole file in memory twice; inline text is passed base64 encoded.
    """
    if document.source_type == "material" and document.source_material_id:
        material = Material.objects.filter(
            pk=document.source_material_id, owner=document.owner
        ).first()
        if material is None:
            raise KnowledgeParseError("来源资料已不存在。", code="source_missing")
        if material.deleted_at is not None:
            raise KnowledgeParseError("来源资料已移入回收站。", code="source_deleted")
        try:
            path = material.storage_key.path
        except (OSError, ValueError) as exc:
            raise KnowledgeParseError("来源资料文件无法读取。", code="source_unreadable") from exc
        return material.original_name, {"path": path}

    if document.source_type == "journal_entry" and document.source_entry_id:
        entry = DailyEntry.objects.filter(
            pk=document.source_entry_id, owner=document.owner
        ).first()
        if entry is None:
            raise KnowledgeParseError("来源记录已不存在。", code="source_missing")
        return (
            f"journal-{entry.date.isoformat()}.md",
            {"text_b64": base64.b64encode(entry.content.encode("utf-8")).decode("ascii")},
        )

    if document.source_type == "manual":
        return (
            f"{document.title}.md",
            {
                "text_b64": base64.b64encode(
                    (document.manual_body or "").encode("utf-8")
                ).decode("ascii")
            },
        )

    if document.source_type == "ai_message" and document.source_message_id:
        from agent.models import Message

        message = Message.objects.filter(
            pk=document.source_message_id, conversation__user=document.owner
        ).first()
        if message is None:
            raise KnowledgeParseError("来源消息已不存在。", code="source_missing")
        return (
            f"message-{message.id}.md",
            {"text_b64": base64.b64encode((message.content or "").encode("utf-8")).decode("ascii")},
        )

    raise KnowledgeParseError("该知识条目没有可解析的来源。", code="no_source")


def _limit_process() -> None:  # pragma: no cover - runs in the child process
    """Apply the address space limit to the parse subprocess."""
    try:
        import resource
    except ImportError:
        # Windows has no rlimit; the timeout still applies.
        return
    try:
        resource.setrlimit(
            resource.RLIMIT_AS, (PARSE_MEMORY_LIMIT_BYTES, PARSE_MEMORY_LIMIT_BYTES)
        )
    except (ValueError, OSError):
        pass


def run_parse_subprocess(filename: str, source: dict) -> dict:
    """Parse a source in a separate process and return its result."""
    backend_dir = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="knowledge-parse-") as workdir:
        input_path = Path(workdir) / "input.json"
        output_path = Path(workdir) / "output.json"
        input_path.write_text(
            json.dumps({"filename": filename, **source}, ensure_ascii=False),
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(backend_dir)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "knowledge.parse_worker", str(input_path), str(output_path)],
                cwd=str(backend_dir),
                env=env,
                capture_output=True,
                timeout=PARSE_TIMEOUT_SECONDS,
                preexec_fn=_limit_process if os.name == "posix" else None,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise KnowledgeParseError(
                f"解析超时（超过 {PARSE_TIMEOUT_SECONDS} 秒）。", code="parse_timeout"
            ) from exc
        if not output_path.exists():
            detail = (completed.stderr or b"").decode("utf-8", errors="replace")[:500]
            logger.warning("Parse subprocess failed: %s", detail)
            raise KnowledgeParseError(
                "解析进程异常退出，未生成索引结果。", code="parse_crashed"
            )
        return json.loads(output_path.read_text(encoding="utf-8"))


def process_job(job: KnowledgeIndexJob, claim_token: str) -> bool:
    """Parse and index one claimed job. Returns True on success."""
    document = KnowledgeDocument.objects.filter(pk=job.document_id).first()
    revision = KnowledgeRevision.objects.filter(pk=job.revision_id).first()
    if document is None or revision is None:
        _fail_job(job, claim_token, "来源已删除。", code="source_missing")
        return False
    if document.deleted_at is not None:
        _fail_job(job, claim_token, "知识条目已移入回收站。", code="document_deleted")
        return False

    try:
        filename, source = _source_payload(document)
        result = run_parse_subprocess(filename, source)
    except KnowledgeParseError as exc:
        _fail_job(job, claim_token, exc.detail, code=exc.code)
        return False

    if not result.get("ok"):
        code = str(result.get("code") or "parse_failed")
        detail = str(result.get("detail") or "解析失败。")
        if code == "needs_ocr":
            _fail_job(
                job,
                claim_token,
                "该文件是扫描件，需要 OCR 才能入库。",
                code="needs_ocr",
                status="needs_ocr",
            )
            return False
        _fail_job(job, claim_token, detail, code=code)
        return False

    if result.get("needs_ocr"):
        _fail_job(
            job,
            claim_token,
            "该文件是扫描件，需要 OCR 才能入库。",
            code="needs_ocr",
            status="needs_ocr",
        )
        return False

    segments = [
        Segment(
            text=item.get("text", ""),
            heading_path=item.get("heading_path", ""),
            page_start=item.get("page_start"),
            page_end=item.get("page_end"),
            char_start=item.get("char_start", 0),
            char_end=item.get("char_end", 0),
        )
        for item in result.get("segments", [])
    ]
    chunks = chunk_segments(segments)
    if not chunks:
        _fail_job(job, claim_token, "没有提取到可索引的文字内容。", code="empty_text")
        return False

    with transaction.atomic():
        current = KnowledgeIndexJob.objects.filter(pk=job.pk).first()
        if current is None or current.claim_token != claim_token:
            # The lease expired or the job was replaced; drop the result.
            logger.info("Dropped stale knowledge job %s", job.pk)
            return False
        document = KnowledgeDocument.objects.filter(pk=document.pk).first()
        if document is None or document.deleted_at is not None:
            return False
        revision = KnowledgeRevision.objects.filter(pk=revision.pk).first()
        if revision is None:
            return False

        try:
            replace_chunks(document, revision, chunks)
        except Exception as exc:  # noqa: BLE001 - quota errors are user facing
            _fail_job(job, claim_token, str(exc), code="quota_exceeded")
            return False

        revision.body = result.get("text", "")
        revision.source_hash = content_hash(result.get("text", ""))
        revision.index_status = "ready"
        revision.error_code = ""
        revision.error_detail = ""
        revision.indexed_at = timezone.now()
        revision.save()
        # Older revisions keep their metadata but release their chunks so
        # they do not occupy the per owner segment quota forever.
        KnowledgeChunk.objects.filter(document=document).exclude(
            revision=revision
        ).delete()
        document.current_revision = revision
        document.save(update_fields=["current_revision"])
        KnowledgeIndexJob.objects.filter(pk=job.pk).update(
            status="done",
            last_error="",
            lease_until=None,
            claim_token="",
            next_run_at=None,
            updated_at=timezone.now(),
        )
    return True


def _fail_job(
    job: KnowledgeIndexJob,
    claim_token: str,
    detail: str,
    *,
    code: str = "parse_failed",
    status: str | None = None,
) -> None:
    revision = KnowledgeRevision.objects.filter(pk=job.revision_id).first()
    if revision is not None:
        revision.index_status = status or "failed"
        revision.error_code = code[:64]
        revision.error_detail = detail[:500]
        revision.save(update_fields=["index_status", "error_code", "error_detail"])
    retryable = status is None and job.attempts < MAX_ATTEMPTS
    now = timezone.now()
    KnowledgeIndexJob.objects.filter(pk=job.pk).update(
        status="pending" if retryable else "failed",
        last_error=detail[:500],
        lease_until=None,
        claim_token="",
        next_run_at=now + timedelta(seconds=RETRY_BACKOFF_SECONDS) if retryable else None,
        updated_at=now,
    )


def reindex_document(document: KnowledgeDocument) -> KnowledgeRevision:
    """Create a new revision and queue a fresh index job."""
    from .ingestion import next_revision_no

    revision = KnowledgeRevision.objects.create(
        document=document,
        revision_no=next_revision_no(document),
        source_version=document.source_version,
        source_hash=content_hash(document.manual_body or ""),
        index_status="pending",
    )
    document.current_revision = revision
    document.save(update_fields=["current_revision"])
    enqueue_job(document, revision)
    return revision


def process_pending(limit: int = 10) -> int:
    """Process up to ``limit`` due jobs; returns the number of successes."""
    processed = 0
    for _ in range(limit):
        claimed = claim_next_job()
        if claimed is None:
            break
        job, token = claimed
        if process_job(job, token):
            processed += 1
    return processed
