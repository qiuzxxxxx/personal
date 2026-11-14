"""Tests for the personal knowledge base and the personal memory."""
from __future__ import annotations

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from agent.models import Conversation, Message
from knowledge.jobs import process_pending
from knowledge.memories import current_floor_epoch
from knowledge.models import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeIndexJob,
    MessageCitation,
    PersonalMemory,
)
from knowledge.search import tokenize
from workspace.models import DailyEntry, Folder, Material, Task

TXT_BYTES = "工作台笔记\n今天需要复核资料库的索引状态。".encode("utf-8")


class KnowledgeTestCase(APITestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="knowledge-test-")
        self.override = override_settings(MEDIA_ROOT=self.tempdir)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.tempdir, True)

        self.owner = User.objects.create_user(username="owner", password="pw-owner-123456")
        self.other = User.objects.create_user(username="other", password="pw-other-123456")
        self.owner_token = Token.objects.create(user=self.owner)
        self.other_token = Token.objects.create(user=self.other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    # -- helpers ---------------------------------------------------------- #
    def upload_material(self, name="note.txt", content=TXT_BYTES, **extra):
        payload = {"file": SimpleUploadedFile(name, content)}
        payload.update(extra)
        return self.client.post("/api/library/materials/", payload, format="multipart")

    def create_note(self, title="测试笔记", body="这是一段中文正文内容。", **extra):
        payload = {"title": title, "manual_body": body}
        payload.update(extra)
        return self.client.post("/api/knowledge/documents/", payload, format="json")

    # -- documents -------------------------------------------------------- #
    def test_create_note_queues_index_job(self):
        response = self.create_note()
        self.assertEqual(response.status_code, 201)
        document_id = response.json()["id"]
        self.assertEqual(response.json()["index_status"], "pending")
        job = KnowledgeIndexJob.objects.get(document__id=document_id)
        self.assertEqual(job.status, "pending")

    def test_worker_indexes_and_search_finds_chinese_text(self):
        response = self.create_note(title="索引测试", body="资料库的索引状态需要复核。")
        document_id = response.json()["id"]
        self.assertEqual(process_pending(), 1)

        document = KnowledgeDocument.objects.get(pk=document_id)
        self.assertEqual(document.index_status, "ready")
        self.assertTrue(KnowledgeChunk.objects.filter(document=document).exists())

        found = self.client.post(
            "/api/knowledge/search/", {"query": "索引状态"}, format="json"
        )
        self.assertEqual(found.status_code, 200)
        self.assertGreaterEqual(found.json()["count"], 1)
        self.assertEqual(found.json()["source_refs"][0], "S1")

    def test_search_without_match_returns_empty_list(self):
        self.create_note(body="完全无关的内容。")
        process_pending()
        found = self.client.post(
            "/api/knowledge/search/", {"query": "不存在的关键词组合"}, format="json"
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["count"], 0)
        self.assertEqual(found.json()["matches"], [])

    def test_document_patch_requires_version(self):
        created = self.create_note()
        document_id = created.json()["id"]
        response = self.client.patch(
            f"/api/knowledge/documents/{document_id}/", {"title": "新标题"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "version_required")

    def test_document_patch_conflict_returns_409(self):
        created = self.create_note()
        document_id = created.json()["id"]
        response = self.client.patch(
            f"/api/knowledge/documents/{document_id}/",
            {"title": "新标题", "version": 99},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "version_conflict")

    def test_delete_moves_to_trash_and_restore_works(self):
        created = self.create_note()
        document_id = created.json()["id"]
        deleted = self.client.delete(f"/api/knowledge/documents/{document_id}/")
        self.assertEqual(deleted.status_code, 200)
        listing = self.client.get("/api/knowledge/documents/")
        self.assertEqual(listing.json()["count"], 0)
        trash = self.client.get("/api/knowledge/documents/?deleted=true")
        self.assertEqual(trash.json()["count"], 1)

        restored = self.client.post(f"/api/knowledge/documents/{document_id}/restore/")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(self.client.get("/api/knowledge/documents/").json()["count"], 1)

    def test_purge_removes_document_only(self):
        created = self.create_note()
        document_id = created.json()["id"]
        purged = self.client.post(f"/api/knowledge/documents/{document_id}/purge/")
        self.assertEqual(purged.status_code, 200)
        self.assertFalse(KnowledgeDocument.objects.filter(pk=document_id).exists())

    # -- import ----------------------------------------------------------- #
    def test_import_material_requires_own_material(self):
        material_id = str(self.upload_material().json()["id"])
        response = self.client.post(
            "/api/knowledge/documents/import/",
            {"material": material_id, "ai_enabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["source_type"], "material")
        self.assertTrue(response.json()["ai_enabled"])

    def test_import_rejects_other_account_material(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        material_id = str(self.upload_material().json()["id"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(
            "/api/knowledge/documents/import/", {"material": material_id}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_import_material_twice_is_rejected(self):
        material_id = str(self.upload_material().json()["id"])
        self.client.post(
            "/api/knowledge/documents/import/", {"material": material_id}, format="json"
        )
        again = self.client.post(
            "/api/knowledge/documents/import/", {"material": material_id}, format="json"
        )
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.json()["code"], "duplicate_document")

    def test_import_journal_entry_creates_snapshot(self):
        entry = DailyEntry.objects.create(owner=self.owner, date="2026-11-14", content="今天完成了知识库接口")
        response = self.client.post(
            "/api/knowledge/documents/import/",
            {"entry": str(entry.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["source_type"], "journal_entry")

    def test_import_message_marks_ai_generated(self):
        conversation = Conversation.objects.create(user=self.owner, title="t")
        message = Message.objects.create(
            conversation=conversation, role="assistant", content="模型生成的结论"
        )
        response = self.client.post(
            "/api/knowledge/documents/import/", {"message": str(message.id)}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["content_origin"], "ai_generated")

    def test_import_requires_exactly_one_source(self):
        response = self.client.post("/api/knowledge/documents/import/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    # -- collections ------------------------------------------------------ #
    def test_collection_delete_moves_documents_to_trash(self):
        collection = self.client.post(
            "/api/knowledge/collections/", {"name": "工作台项目"}, format="json"
        )
        self.assertEqual(collection.status_code, 201)
        collection_id = collection.json()["id"]
        created = self.create_note(collection=collection_id)
        self.assertEqual(created.status_code, 201)

        deleted = self.client.delete(f"/api/knowledge/collections/{collection_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/knowledge/documents/").json()["count"], 0)
        self.assertEqual(
            self.client.get("/api/knowledge/documents/?deleted=true").json()["count"], 1
        )

    def test_search_scope_collection_only(self):
        first = self.client.post("/api/knowledge/collections/", {"name": "A"}, format="json")
        second = self.client.post("/api/knowledge/collections/", {"name": "B"}, format="json")
        self.create_note(title="甲", body="只在甲集合的资料。", collection=first.json()["id"])
        self.create_note(title="乙", body="只在乙集合的资料。", collection=second.json()["id"])
        process_pending()

        response = self.client.post(
            "/api/knowledge/search/",
            {"query": "集合", "scope": "collections", "collection_ids": [first.json()["id"]]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()["matches"]]
        self.assertTrue(titles)
        self.assertTrue(all(title == "甲" for title in titles))

    def test_search_rejects_foreign_collection(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        foreign = self.client.post(
            "/api/knowledge/collections/", {"name": "别人的"}, format="json"
        ).json()["id"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(
            "/api/knowledge/search/",
            {"query": "x", "scope": "collections", "collection_ids": [foreign]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # -- ownership -------------------------------------------------------- #
    def test_other_account_cannot_read_document(self):
        document_id = self.create_note().json()["id"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.get(f"/api/knowledge/documents/{document_id}/")
        self.assertEqual(response.status_code, 404)

    def test_other_account_cannot_search_owner_content(self):
        self.create_note(body="仅所有者可见的资料内容。")
        process_pending()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.post(
            "/api/knowledge/search/", {"query": "仅所有者"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_guest_account_cannot_use_knowledge(self):
        guest = User.objects.create_user(username="yk", password="pw-guest-123456")
        guest.is_staff = False
        guest.save()
        token = Token.objects.create(user=guest)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/knowledge/documents/")
        self.assertEqual(response.status_code, 403)

    # -- memories --------------------------------------------------------- #
    def test_memory_crud_and_conflict(self):
        created = self.client.post(
            "/api/knowledge/memories/",
            {"key": "editor_pref", "content": "回答时使用简体中文。"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        memory_id = created.json()["id"]
        self.assertEqual(created.json()["status"], "active")

        conflict = self.client.patch(
            f"/api/knowledge/memories/{memory_id}/",
            {"content": "换一种语言", "version": 99},
            format="json",
        )
        self.assertEqual(conflict.status_code, 409)

        updated = self.client.patch(
            f"/api/knowledge/memories/{memory_id}/",
            {"content": "回答时使用简体中文，并给出来源。", "version": created.json()["version"]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)

    def test_forget_clears_body_and_raises_floor(self):
        created = self.client.post(
            "/api/knowledge/memories/", {"key": "secret", "content": "临时内容"}, format="json"
        )
        memory_id = created.json()["id"]
        before = current_floor_epoch(self.owner)

        forgotten = self.client.post(
            f"/api/knowledge/memories/{memory_id}/forget/",
            {"version": created.json()["version"]},
            format="json",
        )
        self.assertEqual(forgotten.status_code, 200)
        self.assertEqual(forgotten.json()["status"], "forgotten")
        self.assertEqual(forgotten.json()["content"], "")
        self.assertGreater(current_floor_epoch(self.owner), before)
        self.assertFalse(PersonalMemory.objects.get(pk=memory_id).content)

    def test_duplicate_active_key_is_rejected(self):
        payload = {"key": "dup", "content": "第一次"}
        self.assertEqual(
            self.client.post("/api/knowledge/memories/", payload, format="json").status_code,
            201,
        )
        again = self.client.post("/api/knowledge/memories/", payload, format="json")
        self.assertEqual(again.status_code, 400)

    def test_export_excludes_forgotten_body(self):
        created = self.client.post(
            "/api/knowledge/memories/", {"key": "gone", "content": "不该出现在导出里"}, format="json"
        )
        self.client.post(
            f"/api/knowledge/memories/{created.json()['id']}/forget/",
            {"version": created.json()["version"]},
            format="json",
        )
        export = self.client.get("/api/knowledge/export/")
        self.assertEqual(export.status_code, 200)
        body = export.json()
        self.assertNotIn("不该出现在导出里", str(body))

    # -- write intents ---------------------------------------------------- #
    def test_write_intent_is_idempotent(self):
        payload = {"target": "memory", "idempotency_key": "abc-123"}
        first = self.client.post("/api/knowledge/write-intents/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        second = self.client.post("/api/knowledge/write-intents/", payload, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])

    def test_write_intent_rejects_unknown_target(self):
        response = self.client.post(
            "/api/knowledge/write-intents/",
            {"target": "anything", "idempotency_key": "k"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # -- citations -------------------------------------------------------- #
    def test_citation_of_other_account_is_not_found(self):
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

    # -- tokenizing -------------------------------------------------------- #
    def test_tokenizer_handles_chinese_and_latin(self):
        terms = tokenize("PDF 索引 Index")
        self.assertIn("pdf", terms)
        self.assertIn("索引", terms)
        self.assertIn("index", terms)
        self.assertNotIn("索", terms)


class WorkspaceContextTestCase(APITestCase):
    """The AI context must reflect live task data, not a stored summary."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw-owner-123456")
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_today_task_is_visible_in_workspace_context(self):
        from workspace.views import local_today

        Task.objects.create(
            owner=self.owner,
            title="复核索引",
            status="todo",
            scheduled_date=local_today(self.owner),
        )
        from knowledge.context import build_context

        context = build_context(self.owner, "今天做什么", {"use_workspace": True})
        self.assertIn("复核索引", context.workspace_block)
        self.assertTrue(context.sources)

    def test_workspace_block_is_absent_when_switch_off(self):
        from workspace.views import local_today

        Task.objects.create(
            owner=self.owner,
            title="复核索引",
            status="todo",
            scheduled_date=local_today(self.owner),
        )
        from knowledge.context import build_context

        context = build_context(self.owner, "今天做什么", {"use_workspace": False})
        self.assertEqual(context.workspace_block, "")

    def test_memory_block_uses_only_active_memories(self):
        from knowledge.context import build_context
        from knowledge.memories import create_memory

        create_memory(self.owner, key="a", content="偏好 A", status="active")
        create_memory(self.owner, key="b", content="候选 B", status="suggested")
        context = build_context(self.owner, "你好", {"use_personal_memory": True})
        self.assertIn("偏好 A", context.memory_block)
        self.assertNotIn("候选 B", context.memory_block)
