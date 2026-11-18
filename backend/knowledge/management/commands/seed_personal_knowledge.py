"""Seed the confirmed personal entries of one account.

Only the entries that are verifiable from the 2026-11-14 handover conversation
are created. The command is idempotent: it never overwrites an edited,
disabled or forgotten entry, and it never runs for every account.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledge.memories import MemoryError, create_memory
from knowledge.models import KnowledgeCollection, PersonalMemory
from workspace.models import Project

SOURCE_REF = "2026-11-14 用户在本项目交接对话中的明确要求"

SEED_ENTRIES = [
    {
        "key": "workbench_goal",
        "content": "用户希望将现有项目建设为个人工作台，记录每天要做的事情，并逐步扩展个人管理功能。",
        "kind": "goal",
    },
    {
        "key": "mobile_material_input",
        "content": "用户需要手机扫码上传资料，并能在电脑端继续使用这些资料。",
        "kind": "fact",
    },
    {
        "key": "server_deployment_goal",
        "content": "用户计划后续将项目部署到服务器；当前没有在本交接中提供真实服务器和域名信息。",
        "kind": "goal",
    },
    {
        "key": "preserve_existing_features",
        "content": "对本项目审查和修复时，应保留已有业务功能。用户已授权直接进行本项目普通代码修改与安全修复，不需要逐项重复确认。",
        "kind": "preference",
    },
    {
        "key": "api_connectivity_requirement",
        "content": "用户需要可检测模型 API 是否联通的功能。",
        "kind": "fact",
    },
    {
        "key": "implementation_handoff_preference",
        "content": "本次开发需要详细、可执行的 Trae 交接文档，包含实施步骤和验收要求。",
        "kind": "preference",
    },
    {
        "key": "personal_knowledge_goal",
        "content": "用户需要供 AI 使用的个人知识库，并希望结合已知需求进行个性化。",
        "kind": "goal",
    },
]

PROJECT_NAME = "缺页中断"
COLLECTION_NAME = "工作台项目"


class Command(BaseCommand):
    help = "为指定账号初始化本项目已确认的个人条目（幂等）。"

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="目标账号用户名。")
        parser.add_argument(
            "--dry-run", action="store_true", help="只显示将要写入的条目，不实际写入。"
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        username = str(options["owner"]).strip()
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"账号 {username} 不存在。")

        dry_run = bool(options["dry_run"])
        project = Project.objects.filter(owner=user, name=PROJECT_NAME).first()
        collection = KnowledgeCollection.objects.filter(
            owner=user, name=COLLECTION_NAME
        ).first()

        created = 0
        skipped = 0
        for entry in SEED_ENTRIES:
            existing = PersonalMemory.objects.filter(
                owner=user, key=entry["key"], seed_key=entry["key"]
            ).first()
            if existing is not None:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"[dry-run] 将创建记忆 {entry['key']}")
                created += 1
                continue
            with transaction.atomic():
                if project is None:
                    project = Project.objects.create(
                        owner=user,
                        name=PROJECT_NAME,
                        description="缺页中断 个人工作台项目范围。",
                    )
                if collection is None:
                    collection = KnowledgeCollection.objects.create(
                        owner=user,
                        name=COLLECTION_NAME,
                        description="与 缺页中断 项目相关的知识集合。",
                        project=project,
                    )
                try:
                    create_memory(
                        user,
                        key=entry["key"],
                        content=entry["content"],
                        kind=entry["kind"],
                        scope_type="project",
                        project=project,
                        evidence_type="user_explicit",
                        source_ref=SOURCE_REF,
                        status="active",
                        seed_key=entry["key"],
                    )
                except MemoryError as exc:
                    self.stderr.write(f"跳过 {entry['key']}：{exc.detail}")
                    skipped += 1
                    continue
            created += 1

        self.stdout.write(f"新建 {created} 条，跳过 {skipped} 条已有条目。")
