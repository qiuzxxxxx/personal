"""Run the persistent knowledge index worker."""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from knowledge.jobs import process_pending


class Command(BaseCommand):
    help = (
        "处理知识库索引作业。默认持续循环直到收到终止信号；"
        "--once 只执行一批后退出，--max-batches 限制循环批次数。"
    )

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="只处理一批作业后退出。")
        parser.add_argument("--limit", type=int, default=10, help="单批最多处理的作业数。")
        parser.add_argument("--interval", type=float, default=3.0, help="循环模式的间隔秒数。")
        parser.add_argument(
            "--max-batches",
            type=int,
            default=0,
            help="循环模式最多运行的批次数；0 表示一直运行。",
        )

    def handle(self, *args, **options):
        limit = max(1, options["limit"])
        max_batches = options["max_batches"]
        if options["once"]:
            processed = process_pending(limit)
            self.stdout.write(f"已处理 {processed} 个作业。")
            return

        batches = 0
        while max_batches == 0 or batches < max_batches:
            processed = process_pending(limit)
            batches += 1
            self.stdout.write(f"第 {batches} 批：处理 {processed} 个作业。")
            if processed == 0:
                time.sleep(max(0.5, options["interval"]))
