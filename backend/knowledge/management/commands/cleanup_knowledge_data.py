"""Clean up stale knowledge data: failed staging, expired leases, orphans."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeIndexJob, KnowledgeRevision


class Command(BaseCommand):
    help = "清理失败作业残留、过期租约与已删除条目的分段。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="只统计将要清理的数据，不实际删除。"
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        now = timezone.now()

        expired_jobs = KnowledgeIndexJob.objects.filter(
            status="processing", lease_until__lt=now
        )
        orphan_chunks = KnowledgeChunk.objects.filter(
            document__deleted_at__isnull=False
        )
        orphan_revisions = KnowledgeRevision.objects.filter(
            document__deleted_at__isnull=False
        )
        orphan_jobs = KnowledgeIndexJob.objects.filter(
            document__deleted_at__isnull=False
        )
        failed_jobs = KnowledgeIndexJob.objects.filter(
            status="failed", attempts__gte=3
        )

        counts = {
            "expired_jobs": expired_jobs.count(),
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
        self.stdout.write("清理完成。")
