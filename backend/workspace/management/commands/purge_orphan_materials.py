"""Remove material files that no longer belong to a live database record."""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from workspace.models import Material


class Command(BaseCommand):
    help = "清理私人资料库中的孤儿文件与已删除记录对应的磁盘文件。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="软删除记录保留天数，超过后连同磁盘文件一起清理（默认 30 天）。",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="真正执行删除；默认只做演练。",
        )

    def handle(self, *args, **options):
        days = options["days"]
        execute = options["execute"]
        cutoff = timezone.now() - timedelta(days=days)

        expired = Material.objects.filter(
            deleted_at__isnull=False, deleted_at__lt=cutoff
        )
        live_paths = set(
            Material.objects.filter(deleted_at__isnull=True).values_list(
                "storage_key", flat=True
            )
        )

        removed = 0
        for material in expired:
            path = material.storage_key.path if material.storage_key else None
            if execute and path:
                try:
                    from pathlib import Path

                    Path(path).unlink(missing_ok=True)
                except OSError as exc:  # pragma: no cover - defensive
                    self.stderr.write(f"删除失败 {path}: {exc}")
                    continue
            material.delete()
            removed += 1

        self.stdout.write(
            f"软删除超期记录：{removed} 条（{'已删除' if execute else '演练'}，保留期 {days} 天）"
        )
        self.stdout.write(f"仍在使用的文件：{len(live_paths)} 个")
