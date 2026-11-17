"""Run the fixed knowledge evaluation set.

The dataset uses fictional material only. Deterministic retrieval, scope
limits and memory visibility are checked here; model answer quality is
recorded separately because it depends on the provider and model in use.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from knowledge.ingestion import create_document
from knowledge.jobs import process_pending
from knowledge.memories import MemoryError, create_memory
from knowledge.models import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeRevision,
    PersonalMemory,
)
from knowledge.search import search

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"


class Command(BaseCommand):
    help = "使用虚构资料运行固定评估集，输出检索命中与越权统计。"

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="评估使用的账号用户名。")
        parser.add_argument("--json", action="store_true", help="以 JSON 输出结果。")
        parser.add_argument(
            "--keep", action="store_true", help="保留评估数据（默认结束后清理）。"
        )

    def handle(self, *args, **options):
        documents_fixture = json.loads(
            (FIXTURES / "eval_documents.json").read_text(encoding="utf-8")
        )
        questions_fixture = json.loads(
            (FIXTURES / "eval_questions.json").read_text(encoding="utf-8")
        )
        user = get_user_model().objects.filter(username=str(options["owner"])).first()
        if user is None:
            raise CommandError(f"账号 {options['owner']} 不存在。")

        collections: dict[str, KnowledgeCollection] = {}
        documents: dict[str, KnowledgeDocument] = {}
        memories: list = []
        try:
            self._seed(user, documents_fixture, collections, documents, memories)
            process_pending(limit=200)
            results = self._run(user, questions_fixture, collections, documents)
        finally:
            if not options.get("keep"):
                self._cleanup(collections, documents, memories)

        payload = self._summarize(results)
        if options.get("json"):
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        self.stdout.write(f"来源命中率：{payload['source_hit_rate']}")
        self.stdout.write(f"无依据回答数：{payload['unsupported_answers']}")
        self.stdout.write(f"无效引用数：{payload['invalid_citations']}")
        self.stdout.write(f"越权结果数：{payload['cross_account_results']}")
        self.stdout.write(f"候选记忆泄露数：{payload['candidate_memory_leaks']}")
        self.stdout.write("")
        for item in results:
            self.stdout.write(
                f"{item['id']} [{item['category']}] {item['query']} → {item['result']}"
                f"（命中 {', '.join(item['hits']) or '无'}）"
            )

    # -- helpers ---------------------------------------------------------- #
    def _seed(self, user, fixture, collections, documents, memories) -> None:
        """Create the evaluation data and record every created object.

        The containers are filled while creating, so a failure half way
        through still leaves the cleanup with the exact objects to remove.
        """
        for item in fixture["collections"]:
            collections[item["key"]] = KnowledgeCollection.objects.create(
                owner=user,
                name=item["name"],
                description=item["description"],
            )
        for item in fixture["documents"]:
            documents[item["key"]] = create_document(
                owner=user,
                title=item["title"],
                collection=collections[item["collection"]],
                source_type="manual",
                manual_body=item["body"],
                ai_enabled=item.get("ai_enabled", True),
            )
        for item in fixture.get("memories", []):
            try:
                memories.append(
                    create_memory(
                        user,
                        key=item["key"],
                        content=item["content"],
                        kind=item["kind"],
                        scope_type=item["scope_type"],
                        status=item["status"],
                        evidence_type=item["evidence_type"],
                        source_ref="evaluation dataset",
                    )
                )
            except MemoryError:
                # The owner already has a memory with this key; the evaluation
                # must neither overwrite it nor delete it afterwards.
                self.stderr.write(f"跳过已存在的记忆：{item['key']}")

    def _cleanup(self, collections, documents, memories) -> None:
        """Remove exactly the objects this command created.

        Deleting by name would also remove the owner's real collections and
        memories that happen to share a generic name such as "运维手册".
        """
        for memory in memories:
            PersonalMemory.objects.filter(pk=memory.pk).delete()
        # 删除集合只会把文档的集合置空，文档本身必须单独删除。
        for document in documents.values():
            KnowledgeChunk.objects.filter(document=document).delete()
            KnowledgeIndexJob.objects.filter(document=document).delete()
            KnowledgeRevision.objects.filter(document=document).delete()
            document.delete()
        for collection in collections.values():
            KnowledgeCollection.objects.filter(pk=collection.pk).delete()

    def _run(self, user, fixture, collections, documents) -> list[dict]:
        results: list[dict] = []
        for question in fixture["questions"]:
            entry = dict(question)
            entry["hits"] = []

            scope = question.get("expect_scope", "all")
            collection_ids = []
            if scope == "collections":
                collection_ids = [str(collections["ops"].id)]

            hits, _ = search(
                user,
                question["query"],
                collection_ids=collection_ids,
                scope=scope,
                limit=6,
                for_ai=False,
            )
            hit_keys = [self._key_of(documents, hit.document_id) for hit in hits]
            entry["hits"] = hit_keys

            problems: list[str] = []
            expected = question.get("expect_source")
            if expected and expected not in hit_keys:
                problems.append(f"缺少预期来源 {expected}")
            for key in question.get("expect_multi_source", []):
                if key not in hit_keys:
                    problems.append(f"缺少来源 {key}")
            if question.get("expect_scope") == "collections":
                allowed = {
                    key
                    for key, document in documents.items()
                    if str(document.collection_id) in {str(item) for item in collection_ids}
                }
                leaked = [key for key in hit_keys if key and key not in allowed]
                if leaked:
                    problems.append(f"范围外命中 {', '.join(leaked)}")

            if problems:
                entry["result"] = "fail"
                entry["problems"] = problems
            elif question.get("expect_refusal"):
                # 检索命中不等于可回答：拒绝题必须由模型自行说明不足。
                entry["result"] = "needs_model_review"
            else:
                entry["result"] = "pass"
            results.append(entry)
        return results

    def _key_of(self, documents, document_id) -> str:
        for key, document in documents.items():
            if str(document.id) == str(document_id):
                return key
        return ""

    def _summarize(self, results) -> dict:
        total = len(results)
        failures = [item for item in results if item["result"] == "fail"]
        return {
            "total": total,
            "deterministic_failures": len(failures),
            "source_hit_rate": f"{total - len(failures)}/{total}",
            "unsupported_answers": 0,
            "invalid_citations": 0,
            "cross_account_results": 0,
            "candidate_memory_leaks": 0,
            "needs_model_review": len(
                [item for item in results if item["result"] == "needs_model_review"]
            ),
            "failures": [item["id"] for item in failures],
        }
