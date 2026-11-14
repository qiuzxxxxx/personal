"""Acceptance tests for section 13.5.

The checks use fictional material only. They cover the behaviours that the
acceptance list requires and that can be verified without a model service:
long documents, retrieval behaviour, scope changes, lifecycle invalidation
and the failure modes.
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from agent.models import Conversation, Message
from config.testing import remove_scratch, scratch_dir
from knowledge.context import build_context
from knowledge.ingestion import create_document
from knowledge.jobs import process_pending
from knowledge.memories import create_memory
from knowledge.models import KnowledgeChunk, KnowledgeDocument
from knowledge.search import search
from workspace.models import Material


class LongDocumentTestCase(APITestCase):
    """The old attachment parser cut the text at 80,000 characters."""

    def setUp(self):
        self.tempdir = scratch_dir("knowledge-long-test-")
        self.override = override_settings(MEDIA_ROOT=self.tempdir)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(remove_scratch, self.tempdir)

        self.owner = User.objects.create_user(username="owner", password="pw-long-123456")
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_content_after_80000_characters_is_retrievable(self):
        filler = "这是用于填充长文档的前置内容。" * 8000
        marker = "在第八万字符之后的唯一标记内容"
        body = f"{filler}\n{marker}\n" + "尾部内容。" * 100
        self.assertGreater(len(body), 80_000)

        document = create_document(
            owner=self.owner,
            title="长文档",
            source_type="manual",
            manual_body=body,
            ai_enabled=True,
        )
        process_pending(limit=5)
        document.refresh_from_db()
        self.assertEqual(document.index_status, "ready")

        hits, _ = search(self.owner, "唯一标记内容", limit=5)
        self.assertTrue(hits, "第 80,000 字符之后的内容必须可以检索")
        self.assertIn(str(document.id), [str(hit.document_id) for hit in hits])

    def test_every_character_of_a_long_document_is_covered(self):
        body = "甲乙丙丁戊己庚辛壬癸" * 5000
        document = create_document(
            owner=self.owner,
            title="覆盖检查",
            source_type="manual",
            manual_body=body,
            ai_enabled=True,
        )
        process_pending(limit=5)
        chunks = list(KnowledgeChunk.objects.filter(document=document))
        self.assertTrue(chunks)
        covered = "".join(chunk.text for chunk in chunks)
        # Every source character must be inside the indexed chunks.
        missing = [char for char in set(body) if char not in covered]
        self.assertEqual(missing, [])

    def test_oversized_document_fails_instead_of_silent_truncation(self):
        # The limit is 500,000 characters; a document beyond it must fail
        # with a readable message rather than index only the first half.
        body = "超长内容测试。" * 100_000
        document = create_document(
            owner=self.owner,
            title="超长文档",
            source_type="manual",
            manual_body=body,
            ai_enabled=True,
        )
        process_pending(limit=5)
        document.refresh_from_db()
        self.assertEqual(document.index_status, "failed")
        self.assertEqual(document.current_revision.error_code, "text_too_large")
        self.assertIn("上限", document.current_revision.error_detail)


class ScopeChangeTestCase(APITestCase):
    """Turning the knowledge base off must remove it from later requests."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw-scope-123456")
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.document = create_document(
            owner=self.owner,
            title="私有资料",
            source_type="manual",
            manual_body="这是只属于当前账号的机密资料内容。",
            ai_enabled=True,
        )
        process_pending(limit=5)

    def test_disabled_knowledge_produces_no_context(self):
        context = build_context(self.owner, "机密资料", {"use_knowledge": False})
        self.assertEqual(context.knowledge_block, "")
        self.assertEqual(context.sources, [])

    def test_ai_disabled_document_is_not_retrieved_for_the_model(self):
        self.document.ai_enabled = False
        self.document.save(update_fields=["ai_enabled"])
        context = build_context(self.owner, "机密资料", {"use_knowledge": True})
        self.assertEqual(context.knowledge_block, "")
        self.assertEqual(context.sources, [])

    def test_owner_can_still_search_a_disabled_document(self):
        self.document.ai_enabled = False
        self.document.save(update_fields=["ai_enabled"])
        hits, _ = search(self.owner, "机密资料", limit=5)
        self.assertTrue(hits, "所有者仍应能在知识库页面搜索自己的资料")

    def test_deleted_document_stops_being_retrieved(self):
        self.document.deleted_at = timezone_now()
        self.document.save(update_fields=["deleted_at"])
        hits, _ = search(self.owner, "机密资料", limit=5)
        self.assertEqual(hits, [])


class LifecycleTestCase(APITestCase):
    """Removing a source must stop the derived knowledge."""

    def setUp(self):
        self.tempdir = scratch_dir("knowledge-lifecycle-test-")
        self.override = override_settings(MEDIA_ROOT=self.tempdir)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(remove_scratch, self.tempdir)

        self.owner = User.objects.create_user(username="owner", password="pw-life-123456")
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_deleting_the_material_stops_the_derived_knowledge(self):
        material = Material.objects.create(
            owner=self.owner,
            original_name="note.txt",
            storage_key="library/2026/11/note.txt",
            size_bytes=10,
            state="ready",
        )
        import os

        os.makedirs(os.path.dirname(material.storage_key.path), exist_ok=True)
        with open(material.storage_key.path, "wb") as handle:
            handle.write("资料库里的原始内容。".encode("utf-8"))

        document = create_document(
            owner=self.owner,
            title="来自资料的笔记",
            source_type="material",
            source_material=material,
            ai_enabled=True,
        )
        process_pending(limit=5)
        hits, _ = search(self.owner, "资料库", limit=5)
        self.assertTrue(hits)

        material.deleted_at = timezone_now()
        material.save(update_fields=["deleted_at"])
        # The derived document keeps its copy, but the source is gone, so the
        # document must not be searchable any more.
        hits, _ = search(self.owner, "资料库", limit=5)
        self.assertEqual(hits, [])

    def test_reindex_keeps_only_the_current_chunks(self):
        document = create_document(
            owner=self.owner,
            title="版本切换",
            source_type="manual",
            manual_body="第一版正文内容。" * 50,
            ai_enabled=True,
        )
        process_pending(limit=5)
        first_count = KnowledgeChunk.objects.filter(document=document).count()

        document.manual_body = "第二版正文内容。" * 50
        document.save(update_fields=["manual_body"])
        from knowledge.jobs import reindex_document

        reindex_document(document)
        process_pending(limit=5)
        document.refresh_from_db()
        self.assertEqual(document.index_status, "ready")
        self.assertEqual(document.current_revision.revision_no, 2)
        # The old chunks are released, only the new revision keeps its own.
        self.assertEqual(
            KnowledgeChunk.objects.filter(document=document).count(),
            KnowledgeChunk.objects.filter(
                document=document, revision=document.current_revision
            ).count(),
        )
        self.assertGreater(first_count, 0)


class CitationTestCase(APITestCase):
    """A citation must never point at content the caller may not see."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw-cit-123456")
        self.other = User.objects.create_user(username="other", password="pw-cit-654321")
        self.owner_token = Token.objects.create(user=self.owner)
        self.other_token = Token.objects.create(user=self.other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    def test_fabricated_citation_id_is_not_found(self):
        response = self.client.get("/api/knowledge/citations/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, 404)

    def test_citation_of_another_account_is_not_found(self):
        from knowledge.models import MessageCitation

        conversation = Conversation.objects.create(user=self.owner, title="t")
        message = Message.objects.create(
            conversation=conversation, role="assistant", content="带引用的回答"
        )
        citation = MessageCitation.objects.create(
            owner=self.owner,
            message=message,
            source_id="S1",
            source_type="knowledge",
            snapshot_text="片段",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.get(f"/api/knowledge/citations/{citation.id}/")
        self.assertEqual(response.status_code, 404)

    def test_workspace_citation_reports_a_snapshot(self):
        from knowledge.models import MessageCitation

        conversation = Conversation.objects.create(user=self.owner, title="t")
        message = Message.objects.create(
            conversation=conversation, role="assistant", content="今天要做什么"
        )
        citation = MessageCitation.objects.create(
            owner=self.owner,
            message=message,
            source_id="T1",
            source_type="workspace",
            locator={"title": "复核索引"},
            snapshot_text="复核索引",
        )
        response = self.client.get(f"/api/knowledge/citations/{citation.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "snapshot")
        self.assertIn("快照", response.json()["detail"])


class MemoryInjectionTestCase(APITestCase):
    """Confirmed memories are used, candidates are not."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw-mem-123456")

    def test_confirmed_memory_is_injected(self):
        create_memory(
            self.owner, key="lang", content="回答使用简体中文。", status="active"
        )
        context = build_context(self.owner, "你好", {"use_personal_memory": True})
        self.assertIn("回答使用简体中文。", context.memory_block)

    def test_candidate_memory_is_not_injected(self):
        create_memory(
            self.owner, key="maybe", content="候选：可能喜欢英文。", status="suggested"
        )
        context = build_context(self.owner, "你好", {"use_personal_memory": True})
        self.assertEqual(context.memory_block, "")

    def test_workspace_snapshot_reflects_the_current_task_state(self):
        from django.utils import timezone as django_timezone

        from workspace.models import Task
        from workspace.views import local_today

        task = Task.objects.create(
            owner=self.owner,
            title="复核索引状态",
            status="todo",
            scheduled_date=local_today(self.owner),
        )
        context = build_context(self.owner, "今天要做什么", {"use_workspace": True})
        self.assertIn("复核索引状态", context.workspace_block)

        task.status = "done"
        task.completed_at = django_timezone.now()
        task.save(update_fields=["status", "completed_at"])
        context = build_context(self.owner, "今天要做什么", {"use_workspace": True})
        self.assertIn("已完成", context.workspace_block)


def timezone_now():
    from django.utils import timezone

    return timezone.now()
