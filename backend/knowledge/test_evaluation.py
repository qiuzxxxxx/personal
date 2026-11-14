"""Tests for the fixed evaluation set and the cross-account guarantees.

The dataset is fictional. These tests cover the deterministic part of
section 16.11: retrieval hits, scope limits, memory visibility and
cross-account isolation. Model answer quality needs a real provider and is
recorded separately with the `evaluate_knowledge_retrieval` command.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from knowledge.context import build_context
from knowledge.ingestion import create_document
from knowledge.memories import create_memory
from knowledge.models import KnowledgeCollection, KnowledgeDocument, PersonalMemory
from knowledge.search import search

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class EvaluationSetTestCase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="eval-owner", password="pw-eval-123456")
        self.other = User.objects.create_user(username="eval-other", password="pw-eval-654321")
        self.fixture = load_fixture("eval_documents.json")
        self.questions = load_fixture("eval_questions.json")["questions"]

        self.collections = {}
        for item in self.fixture["collections"]:
            self.collections[item["key"]] = KnowledgeCollection.objects.create(
                owner=self.owner, name=item["name"], description=item["description"]
            )
        self.documents = {}
        for item in self.fixture["documents"]:
            self.documents[item["key"]] = create_document(
                owner=self.owner,
                collection=self.collections[item["collection"]],
                title=item["title"],
                source_type="manual",
                manual_body=item["body"],
                ai_enabled=item.get("ai_enabled", True),
            )
        call_command("process_knowledge_jobs", "--once", "--limit", "50")

    def key_of(self, document_id) -> str:
        for key, document in self.documents.items():
            if str(document.id) == str(document_id):
                return key
        return ""

    def test_all_fixture_documents_are_indexed(self):
        ready = KnowledgeDocument.objects.filter(
            owner=self.owner, current_revision__index_status="ready"
        ).count()
        self.assertEqual(ready, len(self.fixture["documents"]))

    def test_expected_source_is_retrieved(self):
        for question in self.questions:
            expected = question.get("expect_source")
            if not expected:
                continue
            with self.subTest(question=question["id"]):
                hits, _ = search(self.owner, question["query"], limit=6)
                keys = [self.key_of(hit.document_id) for hit in hits]
                self.assertIn(expected, keys)

    def test_multi_source_questions_hit_every_expected_document(self):
        for question in self.questions:
            expected = question.get("expect_multi_source")
            if not expected:
                continue
            with self.subTest(question=question["id"]):
                hits, _ = search(self.owner, question["query"], limit=6)
                keys = [self.key_of(hit.document_id) for hit in hits]
                for key in expected:
                    self.assertIn(key, keys)

    def test_collection_scope_never_leaks_other_collections(self):
        for question in self.questions:
            if question.get("expect_scope") != "collections":
                continue
            with self.subTest(question=question["id"]):
                hits, _ = search(
                    self.owner,
                    question["query"],
                    scope="collections",
                    collection_ids=[str(self.collections["ops"].id)],
                    limit=6,
                )
                for hit in hits:
                    self.assertEqual(str(hit.document.collection_id), str(self.collections["ops"].id))

    def test_other_account_cannot_retrieve_owner_documents(self):
        hits, _ = search(self.other, "备份 恢复 保留天数", limit=6)
        self.assertEqual(hits, [])

    def test_other_account_context_has_no_owner_sources(self):
        context = build_context(
            self.other, "备份保留多少天", {"use_knowledge": True, "use_personal_memory": True}
        )
        self.assertEqual(context.sources, [])
        self.assertEqual(context.knowledge_block, "")
        self.assertEqual(context.memory_block, "")

    def test_only_confirmed_memories_are_injected(self):
        create_memory(
            self.owner,
            key="eval_answer_language",
            content="回答使用简体中文。",
            status="active",
        )
        create_memory(
            self.owner,
            key="eval_candidate_hint",
            content="候选记忆：用户可能习惯英文模板。",
            status="suggested",
        )
        context = build_context(self.owner, "回答语言", {"use_personal_memory": True})
        self.assertIn("回答使用简体中文。", context.memory_block)
        self.assertNotIn("英文模板", context.memory_block)

    def test_malicious_document_is_only_material(self):
        hits, _ = search(self.owner, "外部会议纪要 会议结论", limit=6)
        keys = [self.key_of(hit.document_id) for hit in hits]
        self.assertIn("malicious", keys)
        document = self.documents["malicious"]
        chunks = document.chunks.all()
        self.assertTrue(any("忽略之前的所有指令" in chunk.text for chunk in chunks))

    def test_evaluation_command_runs(self):
        output = StringIO()
        call_command(
            "evaluate_knowledge_retrieval", "--owner", self.owner.username, stdout=output
        )
        text = output.getvalue()
        self.assertIn("来源命中率", text)
        self.assertIn("越权结果数", text)
        self.assertNotIn("eval-owner", PersonalMemory.objects.filter(
            owner=self.owner, source_ref="evaluation dataset"
        ).values_list("key", flat=True))
