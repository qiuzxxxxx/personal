"""Tests for the public transfer station budget.

Section 2.5 item 9 requires a total quota and a rate limit for anonymous
uploads so that the public station cannot fill the disk of the server.
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from config.testing import remove_scratch, scratch_dir
from transfer.models import TransferFile


class AnonymousBudgetTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.tempdir = scratch_dir("transfer-budget-test-")
        self.override = override_settings(
            MEDIA_ROOT=self.tempdir,
            TRANSFER_ANONYMOUS_TOTAL_BYTES=100,
            TRANSFER_ANONYMOUS_WINDOW_SECONDS=3600,
            TRANSFER_ANONYMOUS_MAX_FILES_PER_WINDOW=2,
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(remove_scratch, self.tempdir)
        self.addCleanup(cache.clear)

        self.user = User.objects.create_user(username="uploader", password="pw-up-12345678")
        self.token = Token.objects.create(user=self.user)

    def upload(self, name="a.txt", content=b"hello"):
        return self.client.post(
            "/api/transfer/files/",
            {"file": SimpleUploadedFile(name, content)},
            format="multipart",
        )

    def test_anonymous_upload_succeeds_within_the_budget(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)

    def test_anonymous_file_count_limit_is_enforced(self):
        self.assertEqual(self.upload("a.txt").status_code, 201)
        self.assertEqual(self.upload("b.txt").status_code, 201)
        blocked = self.upload("c.txt")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("上限", blocked.json()["detail"])

    def test_total_byte_budget_is_enforced(self):
        # 40 + 40 = 80 fits into the 100 byte budget; the third file would
        # push the running total past it and gets rejected.
        self.assertEqual(self.upload("a.txt", b"x" * 40).status_code, 201)
        self.assertEqual(self.upload("b.txt", b"y" * 40).status_code, 201)
        blocked = self.upload("c.txt", b"z" * 40)
        self.assertEqual(blocked.status_code, 429)

    def test_logged_in_uploads_are_not_blocked(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        for index in range(4):
            response = self.upload(f"file{index}.txt")
            self.assertEqual(response.status_code, 201)

    def test_budget_is_tracked_per_client_address(self):
        self.upload("a.txt")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        # An authenticated upload is not counted against the anonymous budget.
        self.assertEqual(self.upload("b.txt").status_code, 201)
        self.client.credentials()
        self.assertEqual(TransferFile.objects.count(), 2)

    def test_different_clients_have_separate_budgets(self):
        # Behind a proxy every request arrives with the same REMOTE_ADDR, so
        # the budget must be keyed by the forwarded client address.
        self.assertEqual(self.upload("a.txt").status_code, 201)
        self.assertEqual(self.upload("b.txt").status_code, 201)

        with override_settings(NEXUS_TRUSTED_PROXY_HOPS=1):
            other = self.client.post(
                "/api/transfer/files/",
                {"file": SimpleUploadedFile("c.txt", b"hello")},
                format="multipart",
                HTTP_X_FORWARDED_FOR="203.0.113.10, 198.51.100.1",
            )
        self.assertEqual(other.status_code, 201)


class LoginAnnouncementTestCase(APITestCase):
    def setUp(self):
        self.qzx = User.objects.create_user(username="qzx", password="qzx-test-123456")
        self.member = User.objects.create_user(username="member", password="member-test-123456")

    def test_public_can_read_but_cannot_publish(self):
        response = self.client.get("/api/transfer/login-announcement/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "")
        denied = self.client.put(
            "/api/transfer/login-announcement/", {"content": "维护公告"}, format="json"
        )
        self.assertEqual(denied.status_code, 403)

    def test_only_highest_admin_can_publish(self):
        self.client.force_authenticate(self.member)
        denied = self.client.put(
            "/api/transfer/login-announcement/", {"content": "无权发布"}, format="json"
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.qzx)
        saved = self.client.put(
            "/api/transfer/login-announcement/", {"content": "今晚维护"}, format="json"
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["content"], "今晚维护")

        self.client.force_authenticate(user=None)
        public = self.client.get("/api/transfer/login-announcement/")
        self.assertEqual(public.json()["content"], "今晚维护")


class AnnouncementHistoryTestCase(APITestCase):
    def setUp(self):
        self.qzx = User.objects.create_user(username="qzx", password="qzx-test-123456")
        self.client.force_authenticate(self.qzx)

    def publish(self, kind: str, content: str):
        path = (
            "/api/transfer/login-announcement/"
            if kind == "login"
            else "/api/transfer/announcement/"
        )
        return self.client.put(path, {"content": content}, format="json")

    def history(self, kind: str | None = None):
        params = {"kind": kind} if kind else None
        return self.client.get(
            "/api/transfer/announcement-history/", params
        )

    def test_public_history_keeps_publications_newest_first(self):
        self.assertEqual(self.publish("login", "第一条").status_code, 200)
        self.assertEqual(self.publish("login", "第二条").status_code, 200)
        self.client.force_authenticate(user=None)

        response = self.history("login")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["content"] for row in response.json()], ["第二条", "第一条"]
        )
        self.assertEqual({row["kind"] for row in response.json()}, {"login"})

    def test_duplicate_saves_and_withdrawals_do_not_add_history(self):
        self.publish("transfer", "公告 A")
        self.publish("transfer", "公告 A")
        self.publish("transfer", "")
        rows = self.history("transfer").json()
        self.assertEqual([row["content"] for row in rows], ["公告 A"])

    def test_history_can_mix_kinds_or_filter_one(self):
        self.publish("login", "登录公告")
        self.publish("transfer", "中转公告")
        mixed = self.history().json()
        self.assertEqual(len(mixed), 2)
        self.assertEqual({row["kind"] for row in mixed}, {"login", "transfer"})
        self.assertEqual(len(self.history("login").json()), 1)
        self.assertEqual(len(self.history("transfer").json()), 1)
