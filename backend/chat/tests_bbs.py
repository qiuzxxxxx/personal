from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import BBSPost, BBSReply


class BBSForumTests(TestCase):
    def setUp(self):
        self.qzx = User.objects.create_user("qzx", password="test1234")
        self.sqx = User.objects.create_user("sqx", password="test1234")
        self.yk = User.objects.create_user("yk", password="test1234")  # guest
        self.client = APIClient()
        self.client.force_authenticate(self.qzx)

    # --- 帖子 CRUD ---

    def test_create_public_post(self):
        created = self.client.post(
            reverse("bbs-posts"),
            {"title": "公告帖", "content": "这是公开帖子"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        data = created.json()
        self.assertEqual(data["title"], "公告帖")
        self.assertEqual(data["visibility"], "public")
        self.assertEqual(BBSPost.objects.count(), 1)

    def test_create_private_post_with_visible_to(self):
        created = self.client.post(
            reverse("bbs-posts"),
            {
                "title": "私密帖",
                "content": "只有 sqx 能看到",
                "visibility": "private",
                "visible_to": ["sqx"],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        post = BBSPost.objects.get(pk=created.json()["id"])
        self.assertEqual(post.visible_to.count(), 1)
        self.assertTrue(post.visible_to.filter(username="sqx").exists())

    def test_empty_title_and_content_rejected(self):
        resp = self.client.post(
            reverse("bbs-posts"),
            {"title": "", "content": ""},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_guest_cannot_post(self):
        self.client.force_authenticate(self.yk)
        resp = self.client.post(
            reverse("bbs-posts"),
            {"title": "游客发帖", "content": "不行吧"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    # --- 帖子列表 ---

    def test_list_shows_public_and_own_posts(self):
        BBSPost.objects.create(author=self.qzx, title="QZX 的帖", visibility="public")
        BBSPost.objects.create(author=self.sqx, title="SQX 的帖", visibility="public")
        self.client.force_authenticate(self.sqx)
        resp = self.client.get(reverse("bbs-posts"))
        self.assertEqual(resp.status_code, 200)
        ids = [p["id"] for p in resp.json()]
        self.assertIn(str(BBSPost.objects.get(title="QZX 的帖").pk), ids)
        self.assertIn(str(BBSPost.objects.get(title="SQX 的帖").pk), ids)

    def test_private_post_not_visible_to_others(self):
        BBSPost.objects.create(
            author=self.qzx,
            title="私密帖",
            visibility="private",
        )
        self.client.force_authenticate(self.sqx)
        resp = self.client.get(reverse("bbs-posts"))
        self.assertEqual(len(resp.json()), 0)

    def test_private_post_visible_to_specified_user(self):
        post = BBSPost.objects.create(
            author=self.qzx,
            title="指定可见",
            visibility="private",
        )
        post.visible_to.add(self.sqx)
        self.client.force_authenticate(self.sqx)
        resp = self.client.get(reverse("bbs-posts"))
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["title"], "指定可见")

    # --- 帖子详情 ---

    def test_post_detail_includes_replies(self):
        post = BBSPost.objects.create(author=self.qzx, title="有回复的帖")
        BBSReply.objects.create(post=post, author=self.sqx, content="回复内容")
        self.client.force_authenticate(self.qzx)
        resp = self.client.get(reverse("bbs-post-detail", args=[post.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["replies"]), 1)
        self.assertEqual(resp.json()["replies"][0]["content"], "回复内容")

    # --- 回复 ---

    def test_add_reply(self):
        post = BBSPost.objects.create(author=self.qzx, title="可回复的帖")
        self.client.force_authenticate(self.sqx)
        resp = self.client.post(
            reverse("bbs-post-replies", args=[post.pk]),
            {"content": "我来回一个"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(BBSReply.objects.count(), 1)
        reply = BBSReply.objects.first()
        self.assertEqual(reply.content, "我来回一个")
        self.assertEqual(reply.author, self.sqx)
        # 帖子计数已更新
        post.refresh_from_db()
        self.assertEqual(post.reply_count, 1)

    def test_empty_reply_rejected(self):
        post = BBSPost.objects.create(author=self.qzx, title="空回复")
        self.client.force_authenticate(self.sqx)
        resp = self.client.post(
            reverse("bbs-post-replies", args=[post.pk]),
            {"content": ""},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    # --- 文件附件 ---

    def test_post_with_file(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            file_data = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
            resp = self.client.post(
                reverse("bbs-posts"),
                {"title": "带文件", "content": "附件测试", "file": file_data},
                format="multipart",
            )
            self.assertEqual(resp.status_code, 201)
            post = BBSPost.objects.get(pk=resp.json()["id"])
            self.assertTrue(bool(post.file))
            download = self.client.get(resp.json()["file_url"])
            self.assertEqual(download.status_code, 200)
            download.close()

    def test_reply_with_file(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            post = BBSPost.objects.create(author=self.qzx, title="带回复文件")
            file_data = SimpleUploadedFile("image.png", b"\x89PNG\r\n", content_type="image/png")
            self.client.force_authenticate(self.sqx)
            resp = self.client.post(
                reverse("bbs-post-replies", args=[post.pk]),
                {"content": "看图", "file": file_data},
                format="multipart",
            )
            self.assertEqual(resp.status_code, 201)
            reply = BBSReply.objects.first()
            self.assertTrue(bool(reply.file))
            download = self.client.get(resp.json()["file_url"])
            self.assertEqual(download.status_code, 200)
            download.close()

    # 文件下载已在 chat.tests 中覆盖，此处省略。

    # --- 删除 ---

    def test_author_can_delete_post(self):
        post = BBSPost.objects.create(author=self.qzx, title="我的帖")
        self.client.force_authenticate(self.qzx)
        resp = self.client.delete(reverse("bbs-post-detail", args=[post.pk]))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(BBSPost.objects.filter(pk=post.pk).exists())

    def test_non_author_cannot_delete_post(self):
        post = BBSPost.objects.create(author=self.qzx, title="别人的帖")
        self.client.force_authenticate(self.sqx)
        resp = self.client.delete(reverse("bbs-post-detail", args=[post.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(BBSPost.objects.filter(pk=post.pk).exists())

    def test_admin_can_delete_any_post(self):
        post = BBSPost.objects.create(author=self.sqx, title="管理员删帖")
        self.client.force_authenticate(self.qzx)
        resp = self.client.delete(reverse("bbs-post-detail", args=[post.pk]))
        self.assertEqual(resp.status_code, 204)

    def test_author_can_delete_own_reply(self):
        post = BBSPost.objects.create(author=self.qzx, title="删回复")
        reply = BBSReply.objects.create(post=post, author=self.sqx, content="要删的")
        self.client.force_authenticate(self.sqx)
        resp = self.client.delete(
            reverse("bbs-reply-detail", args=[post.pk, reply.pk])
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(BBSReply.objects.filter(pk=reply.pk).exists())
        post.refresh_from_db()
        self.assertEqual(post.reply_count, 0)
