"""Rebuild the knowledge index from the stored originals."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from knowledge.jobs import reindex_document
from knowledge.models import KnowledgeDocument


class Command(BaseCommand):
    help = "为知识条目创建新修订并重新排队索引。"

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="只重建指定账号的条目。")
        parser.add_argument("--document", help="只重建指定条目（UUID）。")
        parser.add_argument(
            "--dry-run", action="store_true", help="只显示将要重建的条目，不实际执行。"
        )

    def handle(self, *args, **options):
        queryset = KnowledgeDocument.objects.filter(deleted_at__isnull=True)
        if options.get("owner"):
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.filter(username=options["owner"]).first()
            if user is None:
                self.stderr.write("账号不存在。")
                return
            queryset = queryset.filter(owner=user)
        if options.get("document"):
            queryset = queryset.filter(pk=options["document"])

        count = 0
        for document in queryset.select_related("current_revision"):
            if options.get("dry_run"):
                self.stdout.write(f"[dry-run] 将重建 {document.title}（{document.id}）")
                count += 1
                continue
            reindex_document(document)
            count += 1
        self.stdout.write(f"已排队重建 {count} 个知识条目。")
