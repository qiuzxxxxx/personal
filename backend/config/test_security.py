import socket
from unittest.mock import patch

import httpx
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APIRequestFactory

from agent.crypto import encrypt_secret
from agent.endpoints import LLMError, ModelTransport
from agent.models import UserApiConfig
from agent.views import _merge_saved_config
from accounts.models import ActivityLog
from config.asgi import application
from transfer.models import TransferFile


class AccountAndFileTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user("qzx")
        self.admin = User.objects.create_user("sqx")
        self.guest = User.objects.create_user("yk")
        self.client = APIClient()

    def test_scoped_logs_and_password_resets(self):
        ActivityLog.objects.create(user=self.super_admin, action="login")
        ActivityLog.objects.create(user=self.guest, action="login")
        ActivityLog.objects.create(user=self.guest, actor=self.super_admin, action="password_changed")
        self.client.force_authenticate(self.admin)
        logs = reverse("auth-logs")
        self.assertEqual(self.client.get(logs, {"username": "qzx"}).status_code, 403)
        self.assertEqual(self.client.get(logs, {"limit": "invalid"}).status_code, 400)
        self.assertEqual(
            [item["username"] for item in self.client.get(logs, {"scope": "all"}).json()],
            ["yk"],
        )
        token = Token.objects.create(user=self.guest)
        response = self.client.post(
            reverse("auth-change-password", args=["yk"]),
            {"new_password": "a-new-test-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.post(reverse("auth-change-password", args=["qzx"]), {}).status_code, 403)

    def test_login_limit_uses_socket_address(self):
        cache.clear()
        self.addCleanup(cache.clear)
        # The limiter buckets by wall-clock; pin the clock so a 5-minute
        # boundary cannot reset the counters in the middle of this test.
        with patch("accounts.views.time", return_value=1_700_000_000.0):
            for count in range(13):
                response = self.client.post(
                    reverse("auth-login"),
                    {"username": "qzx", "password": "incorrect"},
                    HTTP_X_FORWARDED_FOR=f"192.0.2.{count + 1}",
                )
                self.assertEqual(response.status_code, 401 if count < 12 else 429)

    def test_private_transfer_uses_owner_id(self):
        anonymous = TransferFile.objects.create(uploader_name="yk", is_public=False)
        owned = TransferFile.objects.create(
            uploader_name="a display label", uploader=self.guest, is_public=False
        )
        self.client.force_authenticate(self.guest)
        files = self.client.get("/api/transfer/files/").json()
        self.assertEqual([row["id"] for row in files], [str(owned.pk)])
        self.assertEqual(
            self.client.get(f"/api/transfer/files/{anonymous.pk}/download/").status_code, 403
        )

    @override_settings(NEXUS_BUILTIN_LLM_API_KEY="test-builtin")
    @patch("agent.crypto.get_master_key", return_value=Fernet.generate_key())
    def test_model_credentials_are_bound_to_origin(self, _master_key):
        request = APIRequestFactory().post("/")
        request.user = self.super_admin
        config, error = _merge_saved_config(request, {})
        self.assertIsNone(error)
        self.assertEqual(config["api_key"], "test-builtin")
        config, error = _merge_saved_config(request, {"base_url": "https://models.example.com"})
        self.assertIsNone(error)
        self.assertNotIn("api_key", config)
        UserApiConfig.objects.create(
            user=self.super_admin,
            base_url="https://models.example.com/v1",
            api_key_cipher=encrypt_secret("test-saved-key"),
        )
        config, error = _merge_saved_config(request, {"base_url": "https://models.example.com/v2"})
        self.assertIsNone(error)
        self.assertEqual(config["api_key"], "test-saved-key")
        config, error = _merge_saved_config(request, {"base_url": "https://other.example.com"})
        self.assertIsNone(error)
        self.assertNotIn("api_key", config)


class ModelTransportTests(SimpleTestCase):
    def test_transport_preserves_host_and_connects_to_validated_address(self):
        endpoint = "https://models.example.com/v1/chat/completions"
        dns_result = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with patch("agent.endpoints.socket.getaddrinfo", return_value=dns_result), patch.object(
            httpx.HTTPTransport, "handle_request", return_value=httpx.Response(200)
        ) as send:
            with ModelTransport(endpoint) as transport:
                response = transport.handle_request(httpx.Request("POST", endpoint))
                self.assertEqual(response.status_code, 200)
                pinned = send.call_args.args[0]
                self.assertEqual(pinned.url.host, "8.8.8.8")
                self.assertEqual(pinned.headers["Host"], "models.example.com")
                self.assertEqual(pinned.extensions["sni_hostname"], "models.example.com")

    def test_transport_rejects_private_destinations_and_cross_origin_redirects(self):
        endpoint = "https://models.example.com/v1/chat/completions"
        dns_result = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch("agent.endpoints.socket.getaddrinfo", return_value=dns_result), patch.object(
            httpx.HTTPTransport, "handle_request"
        ) as send:
            with ModelTransport(endpoint) as transport:
                with self.assertRaises(LLMError):
                    transport.handle_request(httpx.Request("POST", endpoint))
                with self.assertRaises(LLMError):
                    transport.handle_request(httpx.Request("POST", "https://other.example.com"))
            send.assert_not_called()


class ChatSocketTests(TransactionTestCase):
    def test_socket_denies_guest_and_revoked_sessions(self):
        qzx = User.objects.create_user("qzx")
        sqx = User.objects.create_user("sqx")
        guest = User.objects.create_user("yk")
        tokens = [Token.objects.create(user=user).key for user in (qzx, sqx, guest)]

        async def exercise():
            # The chat protocol requires a ?with=<username> query string since
            # a991871; qzx may pick any partner, sqx may only chat with qzx.
            sockets = [
                WebsocketCommunicator(
                    application,
                    path,
                    headers=[(b"origin", b"http://localhost:5173")],
                    subprotocols=["zixxx.chat", f"token.{token}"],
                )
                for token, path in (
                    (tokens[0], "/ws/chat/?with=sqx"),
                    (tokens[1], "/ws/chat/?with=qzx"),
                    (tokens[2], "/ws/chat/"),
                )
            ]
            left, right, denied = sockets
            try:
                self.assertEqual(await denied.connect(), (False, 4401))
                self.assertEqual(await left.connect(), (True, "zixxx.chat"))
                self.assertEqual(await right.connect(), (True, "zixxx.chat"))
                self.assertEqual((await left.receive_json_from())["type"], "connected")
                self.assertEqual((await right.receive_json_from())["type"], "connected")
                await left.send_json_to({"type": "message.send", "content": "hello"})
                self.assertEqual((await right.receive_json_from())["message"]["content"], "hello")
                await left.receive_json_from()
                await Token.objects.filter(key=tokens[1]).adelete()
                await left.send_json_to({"type": "typing", "is_typing": True})
                close = await right.receive_output()
                self.assertEqual((close["type"], close["code"]), ("websocket.close", 4401))
            finally:
                for websocket in sockets:
                    await websocket.disconnect()

        async_to_sync(exercise)()


class UpgradeTests(TransactionTestCase):
    def test_upgrade_revokes_default_passwords_and_preserves_provable_ownership(self):
        executor = MigrationExecutor(connection)
        previous = [("accounts", "0001_initial"), ("transfer", "0001_initial")]
        current = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(current))
        old_apps = executor.loader.project_state(previous).apps
        OldTransfer = old_apps.get_model("transfer", "TransferFile")
        old_admin = User.objects.create_user("qzx", password="11408")
        existing_guest = User.objects.create_user("yk", password="test-existing-guest-password")
        old_token = Token.objects.create(user=old_admin)
        guest_token = Token.objects.create(user=existing_guest)
        owned = OldTransfer.objects.create(uploader_name="yk", is_public=False)
        anonymous = OldTransfer.objects.create(uploader_name="arbitrary label", is_public=False)

        MigrationExecutor(connection).migrate(current)
        old_admin.refresh_from_db()
        existing_guest.refresh_from_db()
        self.assertFalse(old_admin.has_usable_password())
        self.assertFalse(Token.objects.filter(key=old_token.key).exists())
        self.assertTrue(existing_guest.check_password("test-existing-guest-password"))
        self.assertTrue(Token.objects.filter(key=guest_token.key).exists())
        self.assertEqual(TransferFile.objects.get(pk=owned.pk).uploader_id, existing_guest.pk)
        self.assertIsNone(TransferFile.objects.get(pk=anonymous.pk).uploader_id)
