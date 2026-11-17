from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import ChatMessage


class ChatUnreadTests(TestCase):
    def setUp(self):
        self.qzx = User.objects.create_user("qzx")
        self.sqx = User.objects.create_user("sqx")
        self.client = APIClient()

    def send_as_qzx(self, content: str):
        self.client.force_authenticate(self.qzx)
        return self.client.post(
            f'{reverse("chat-messages")}?with=sqx', {"content": content}
        )

    def test_unread_count_and_mark_read(self):
        self.assertEqual(self.send_as_qzx("第一条").status_code, 201)
        self.client.force_authenticate(self.sqx)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 1)

        history = self.client.get(reverse("chat-messages"))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 0)

        self.assertEqual(self.send_as_qzx("第二条").status_code, 201)
        self.client.force_authenticate(self.sqx)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 1)
        self.assertEqual(self.client.post(reverse("chat-mark-read")).status_code, 200)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 0)

        self.client.force_authenticate(self.qzx)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 0)

    def test_offline_recipient_can_read_the_message_later(self):
        # 留言不依赖实时连接：对方离线时写入数据库，上线后仍可读取。
        created = self.send_as_qzx("离线留言")
        self.assertEqual(created.status_code, 201)
        self.client.force_authenticate(self.sqx)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 1)
        history = self.client.get(reverse("chat-messages"))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["content"], "离线留言")

    def test_messages_persist_without_burn_fields(self):
        self.client.force_authenticate(self.qzx)
        created = self.client.post(
            f'{reverse("chat-messages")}?with=sqx',
            {"content": "普通留言", "burn_after_read_seconds": 10},
        )
        self.assertEqual(created.status_code, 201)
        payload = created.json()
        self.assertNotIn("burn_after_read_seconds", payload)
        self.assertNotIn("read_at", payload)
        self.assertNotIn("expires_at", payload)

        self.client.force_authenticate(self.sqx)
        history = self.client.get(reverse("chat-messages"))
        self.assertEqual(history.json()[0]["content"], "普通留言")
        # 读取不会触发任何到期或删除。
        self.client.force_authenticate(self.qzx)
        self.assertEqual(len(self.client.get(f'{reverse("chat-messages")}?with=sqx').json()), 1)
        self.assertEqual(ChatMessage.objects.count(), 1)

    def test_delete_for_self_keeps_other_view_and_updates_unread(self):
        created = self.send_as_qzx("只隐藏给接收者")
        message_id = created.json()["id"]
        self.client.force_authenticate(self.sqx)
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 1)
        response = self.client.delete(
            f'{reverse("chat-message-detail", args=[message_id])}?scope=self'
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(reverse("chat-messages")).json(), [])
        self.assertEqual(self.client.get(reverse("chat-unread")).json()["count"], 0)
        self.client.force_authenticate(self.qzx)
        self.assertEqual(len(self.client.get(f'{reverse("chat-messages")}?with=sqx').json()), 1)
        self.assertTrue(ChatMessage.objects.filter(pk=message_id).exists())

    def test_delete_for_everyone_is_rejected_and_record_is_retained(self):
        created = self.send_as_qzx("双方删除")
        message_id = created.json()["id"]
        self.client.force_authenticate(self.sqx)
        response = self.client.delete(
            f'{reverse("chat-message-detail", args=[message_id])}?scope=everyone'
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(ChatMessage.objects.filter(pk=message_id).exists())
        self.assertEqual(len(self.client.get(reverse("chat-messages")).json()), 1)
        self.client.force_authenticate(self.qzx)
        self.assertEqual(len(self.client.get(f'{reverse("chat-messages")}?with=sqx').json()), 1)

    def test_clear_for_self_hides_only_own_list_and_keeps_records(self):
        self.send_as_qzx("第一条")
        self.client.force_authenticate(self.sqx)
        self.client.post(f'{reverse("chat-messages")}?with=qzx', {"content": "第二条"})
        self.client.force_authenticate(self.qzx)
        response = self.client.delete(
            f'{reverse("chat-clear-messages")}?with=sqx&scope=self'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], 2)
        self.assertEqual(self.client.get(f'{reverse("chat-messages")}?with=sqx').json(), [])
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.client.force_authenticate(self.sqx)
        self.assertEqual(len(self.client.get(reverse("chat-messages")).json()), 2)
        self.assertEqual(self.send_as_qzx("新消息").status_code, 201)
        self.assertEqual(len(self.client.get(f'{reverse("chat-messages")}?with=sqx').json()), 1)

    def test_clear_for_everyone_is_rejected(self):
        self.send_as_qzx("保留记录")
        self.client.force_authenticate(self.qzx)
        response = self.client.delete(
            f'{reverse("chat-clear-messages")}?with=sqx&scope=everyone'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ChatMessage.objects.count(), 1)
        self.client.force_authenticate(self.sqx)
        self.assertEqual(len(self.client.get(reverse("chat-messages")).json()), 1)

    def test_mutual_file_transfer_between_both_sides(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            self.client.force_authenticate(self.qzx)
            first = self.client.post(
                f'{reverse("chat-file-upload")}?with=sqx',
                {
                    "file": SimpleUploadedFile(
                        "from-qzx.txt", b"qzx to sqx", content_type="text/plain"
                    ),
                    "content": "给你的文件",
                },
                format="multipart",
            )
            self.assertEqual(first.status_code, 201)
            first_id = first.json()["id"]

            self.client.force_authenticate(self.sqx)
            download = self.client.get(reverse("chat-file-download", args=[first_id]))
            self.assertEqual(download.status_code, 200)
            download.close()

            second = self.client.post(
                f'{reverse("chat-file-upload")}?with=qzx',
                {
                    "file": SimpleUploadedFile(
                        "from-sqx.txt", b"sqx to qzx", content_type="text/plain"
                    ),
                    "content": "回传文件",
                },
                format="multipart",
            )
            self.assertEqual(second.status_code, 201)
            second_id = second.json()["id"]

            self.client.force_authenticate(self.qzx)
            reply = self.client.get(reverse("chat-file-download", args=[second_id]))
            self.assertEqual(reply.status_code, 200)
            reply.close()

            self.assertEqual(ChatMessage.objects.filter(message_type="file").count(), 2)

    def test_file_survives_self_delete_and_cannot_be_erased_for_everyone(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            self.client.force_authenticate(self.qzx)
            upload = SimpleUploadedFile("note.txt", b"private file", content_type="text/plain")
            created = self.client.post(
                f'{reverse("chat-file-upload")}?with=sqx', {"file": upload}, format="multipart"
            )
            self.assertEqual(created.status_code, 201)
            message_id = created.json()["id"]
            file_path = Path(ChatMessage.objects.get(pk=message_id).file.path)
            self.assertTrue(file_path.exists())

            self.assertEqual(self.client.delete(
                f'{reverse("chat-message-detail", args=[message_id])}?scope=self'
            ).status_code, 204)
            self.assertTrue(file_path.exists())
            self.client.force_authenticate(self.sqx)
            download = self.client.get(reverse("chat-file-download", args=[message_id]))
            self.assertEqual(download.status_code, 200)
            download.close()

            blocked = self.client.delete(
                f'{reverse("chat-message-detail", args=[message_id])}?scope=everyone'
            )
            self.assertEqual(blocked.status_code, 400)
            self.assertTrue(file_path.exists())
            self.assertTrue(ChatMessage.objects.filter(pk=message_id).exists())

    def test_unrelated_account_cannot_delete_message(self):
        created = self.send_as_qzx("聊天")
        outsider = User.objects.create_user("outsider")
        self.client.force_authenticate(outsider)
        response = self.client.delete(
            f'{reverse("chat-message-detail", args=[created.json()["id"]])}?scope=self'
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ChatMessage.objects.count(), 1)
