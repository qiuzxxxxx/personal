"""Clean up stale knowledge data: failed staging, expired leases, orphans.

Documents in the trash keep their revisions and chunks for a retention
period.  Purging them immediately would make a restored document a zombie:
the entry would come back without a searchable revision.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeIndexJob, KnowledgeRevision

DEFAULT_RETENTION_DAYS = 30


class Command(BaseCommand):
    help = "清理失败作业残留、过期租约与超过保留期的已删除条目分段。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="只统计将要清理的数据，不实际删除。"
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help="回收站条目的保留天数，超过后才清理其分段、修订与作业（默认 30 天）。",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        retention_days = max(0, int(options["retention_days"]))
        now = timezone.now()
        cutoff = now - timedelta(days=retention_days)

        expired_jobs = KnowledgeIndexJob.objects.filter(
            status="processing", lease_until__lt=now
        )
        # Only documents that have been in the trash longer than the retention
        # period lose their chunks; the rest can still be restored intact.
        expired_documents = KnowledgeDocument.objects.filter(
            deleted_at__isnull=False, deleted_at__lt=cutoff
        )
        orphan_chunks = KnowledgeChunk.objects.filter(document__in=expired_documents)
        orphan_revisions = KnowledgeRevision.objects.filter(document__in=expired_documents)
        orphan_jobs = KnowledgeIndexJob.objects.filter(document__in=expired_documents)
        failed_jobs = KnowledgeIndexJob.objects.filter(
            status="failed", attempts__gte=3
        )

        counts = {
            "expired_jobs": expired_jobs.count(),
            "expired_documents": expired_documents.count(),
            "orphan_chunks": orphan_chunks.count(),
            "orphan_revisions": orphan_revisions.count(),
            "orphan_jobs": orphan_jobs.count(),
            "failed_jobs": failed_jobs.count(),
        }
        self.stdout.write(
            "、".join(f"{key}={value}" for key, value in counts.items())
        )
        if dry_run:
            self.stdout.write("[dry-run] 未删除任何数据。")
            return

        expired_jobs.update(status="pending", lease_until=None, claim_token="")
        orphan_chunks.delete()
        orphan_jobs.delete()
        orphan_revisions.delete()
        failed_jobs.delete()
        self.stdout.write(f"清理完成（回收站保留 {retention_days} 天）。")
