"""Regression tests for the workspace APIs."""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from workspace.models import DailyEntry, Project, Tag, Task


class WorkspaceTestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pw-owner-123456")
        self.other = User.objects.create_user(username="other", password="pw-other-123456")
        self.owner_token = Token.objects.create(user=self.owner)
        self.other_token = Token.objects.create(user=self.other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    # -- helpers ---------------------------------------------------------- #
    def create_task(self, **overrides):
        payload = {"title": "整理今天收到的资料"}
        payload.update(overrides)
        return self.client.post("/api/tasks/", payload, format="json")

    # -- authentication --------------------------------------------------- #
    def test_requires_authentication(self):
        self.client.credentials()
        response = self.client.get("/api/tasks/")
        self.assertEqual(response.status_code, 401)

    # -- task lifecycle --------------------------------------------------- #
    def test_create_and_list_tasks(self):
        response = self.create_task(description="写会议纪要", scheduled_date="2026-11-15")
        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertEqual(created["title"], "整理今天收到的资料")
        self.assertEqual(created["scheduled_date"], "2026-11-15")
        self.assertEqual(created["version"], 1)

        listing = self.client.get("/api/tasks/").json()
        self.assertEqual(listing["count"], 1)

    def test_today_view_groups_tasks(self):
        today = timezone.localtime().date().isoformat()
        self.create_task(title="今天要做", scheduled_date=today)
        self.create_task(title="未安排")
        self.create_task(
            title="已逾期",
            scheduled_date=(timezone.localtime().date() - timedelta(days=3)).isoformat(),
            due_at=(timezone.now() - timedelta(hours=2)).isoformat(),
        )

        payload = self.client.get("/api/workspace/today/").json()
        titles = [task["title"] for task in payload["tasks"]]
        self.assertIn("今天要做", titles)
        self.assertNotIn("未安排", titles)
        self.assertEqual(payload["unscheduled_count"], 1)
        self.assertEqual(payload["overdue_count"], 1)
        self.assertEqual(payload["needs_reschedule_count"], 1)
        self.assertEqual(payload["completed_today"], 0)

    def test_completion_sets_and_clears_completed_at(self):
        created = self.create_task().json()
        version = created["version"]

        done = self.client.patch(
            f"/api/tasks/{created['id']}/",
            {"status": "done", "version": version},
            format="json",
        )
        self.assertEqual(done.status_code, 200)
        self.assertIsNotNone(done.json()["completed_at"])
        done_version = done.json()["version"]

        again = self.client.patch(
            f"/api/tasks/{created['id']}/",
            {"status": "done", "version": done_version},
            format="json",
        )
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["completed_at"], done.json()["completed_at"])

        reopened = self.client.patch(
            f"/api/tasks/{created['id']}/",
            {"status": "todo", "version": again.json()["version"]},
            format="json",
        )
        self.assertIsNone(reopened.json()["completed_at"])

    def test_version_conflict_returns_409(self):
        created = self.create_task().json()
        payload = {"title": "被拒绝的修改", "version": created["version"]}
        self.assertEqual(
            self.client.patch(f"/api/tasks/{created['id']}/", payload, format="json").status_code,
            200,
        )
        conflict = self.client.patch(f"/api/tasks/{created['id']}/", payload, format="json")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], "version_conflict")

    def test_missing_version_is_rejected(self):
        created = self.create_task().json()
        response = self.client.patch(
            f"/api/tasks/{created['id']}/", {"title": "无版本"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_soft_delete_and_restore(self):
        created = self.create_task().json()
        deleted = self.client.delete(f"/api/tasks/{created['id']}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks/").json()["count"], 0)

        trash = self.client.get("/api/tasks/?deleted=true").json()
        self.assertEqual(trash["count"], 1)

        restored = self.client.post(f"/api/tasks/{created['id']}/restore/")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks/").json()["count"], 1)

    def test_client_request_id_is_idempotent(self):
        request_id = str(uuid.uuid4())
        first = self.create_task(client_request_id=request_id)
        second = self.create_task(client_request_id=request_id)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.client.get("/api/tasks/").json()["count"], 1)

        conflicting = self.create_task(client_request_id=request_id, title="别的内容")
        self.assertEqual(conflicting.status_code, 409)

    def test_owner_isolation(self):
        created = self.create_task().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        self.assertEqual(self.client.get("/api/tasks/").json()["count"], 0)
        self.assertEqual(self.client.get(f"/api/tasks/{created['id']}/").status_code, 404)
        self.assertEqual(
            self.client.patch(
                f"/api/tasks/{created['id']}/", {"title": "x", "version": 1}, format="json"
            ).status_code,
            404,
        )

    def test_reorder_updates_positions(self):
        first = self.create_task(title="第一个").json()
        second = self.create_task(title="第二个").json()
        response = self.client.post(
            "/api/tasks/reorder/",
            {
                "items": [
                    {"id": second["id"], "version": second["version"]},
                    {"id": first["id"], "version": first["version"]},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        titles = [task["title"] for task in self.client.get("/api/tasks/").json()["results"]]
        self.assertEqual(titles, ["第二个", "第一个"])

    def test_reorder_rejects_stale_version(self):
        created = self.create_task().json()
        self.client.patch(
            f"/api/tasks/{created['id']}/", {"title": "改名", "version": 1}, format="json"
        )
        response = self.client.post(
            "/api/tasks/reorder/",
            {"items": [{"id": created["id"], "version": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    # -- projects --------------------------------------------------------- #
    def test_project_crud(self):
        created = self.client.post("/api/projects/", {"name": "工作台项目"}, format="json")
        self.assertEqual(created.status_code, 201)
        project_id = created.json()["id"]

        updated = self.client.patch(
            f"/api/projects/{project_id}/",
            {"name": "工作台项目 v2", "version": created.json()["version"]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "工作台项目 v2")

        deleted = self.client.delete(f"/api/projects/{project_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/projects/").json()["count"], 0)

    # -- tags ------------------------------------------------------------- #
    def test_tag_creation_is_idempotent_per_name(self):
        first = self.client.post("/api/tags/", {"name": " 重点 "}, format="json")
        second = self.client.post("/api/tags/", {"name": "重点"}, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])

    # -- journal ---------------------------------------------------------- #
    def test_journal_create_update_and_conflict(self):
        day = timezone.localtime().date().isoformat()
        empty = self.client.get(f"/api/journal/{day}/").json()
        self.assertFalse(empty["exists"])
        self.assertEqual(empty["content"], "")

        created = self.client.put(f"/api/journal/{day}/", {"content": "第一版"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["content"], "第一版")

        conflict = self.client.put(
            f"/api/journal/{day}/", {"content": "冲突", "version": 99}, format="json"
        )
        self.assertEqual(conflict.status_code, 409)

        updated = self.client.put(
            f"/api/journal/{day}/",
            {"content": "第二版", "version": created.json()["version"]},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["content"], "第二版")
        self.assertEqual(DailyEntry.objects.filter(owner=self.owner).count(), 1)

    def test_journal_is_owner_scoped(self):
        day = timezone.localtime().date().isoformat()
        self.client.put(f"/api/journal/{day}/", {"content": "我的记录"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        payload = self.client.get(f"/api/journal/{day}/").json()
        self.assertFalse(payload["exists"])
        self.assertEqual(payload["content"], "")

    # -- preferences ------------------------------------------------------ #
    def test_preferences_update(self):
        response = self.client.patch(
            "/api/workspace/preferences/",
            {"timezone": "Asia/Shanghai", "default_task_priority": "high"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["default_task_priority"], "high")

        invalid = self.client.patch(
            "/api/workspace/preferences/", {"timezone": "Mars/Olympus"}, format="json"
        )
        self.assertEqual(invalid.status_code, 400)
