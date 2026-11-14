from unittest.mock import patch

import httpx
from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .crypto import encrypt_secret
from .models import Conversation, UserApiConfig


class ConnectionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("qzx")
        self.client.force_authenticate(self.user)
        self.url = reverse("agent-config-test")
        self.config = {
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "test-model",
        }

    @override_settings(NEXUS_BUILTIN_LLM_API_KEY="test-builtin")
    def test_probe_uses_current_model_and_does_not_save(self):
        def send(request):
            self.assertEqual(request.headers["Authorization"], "Bearer test-builtin")
            self.assertIn(b'"model":"test-model"', request.content)
            self.assertIn(b'"stream":true', request.content)
            self.assertIn(b"Reply with OK.", request.content)
            self.assertNotIn(b"private prompt", request.content)
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"OK"}}]}\n\n',
            )

        with patch("agent.llm.ModelTransport", return_value=httpx.MockTransport(send)):
            response = self.client.post(
                self.url, {**self.config, "system_prompt": "private prompt"}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["latency_ms"], 0)
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(UserApiConfig.objects.exists())

    def test_upstream_authentication_error_hides_upstream_body(self):
        transport = httpx.MockTransport(
            lambda _: httpx.Response(401, text="untrusted response body")
        )
        with patch("agent.llm.ModelTransport", return_value=transport):
            response = self.client.post(self.url, self.config, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("HTTP 401", response.json()["detail"])
        self.assertNotIn("untrusted response body", response.json()["detail"])

    def test_guest_cannot_probe(self):
        self.client.force_authenticate(User.objects.create_user("yk"))
        with patch("agent.views.check_model_connection") as probe:
            self.assertEqual(self.client.post(self.url, self.config, format="json").status_code, 403)
        probe.assert_not_called()

    @patch("agent.crypto.get_master_key", return_value=Fernet.generate_key())
    def test_probe_uses_saved_key_or_draft_without_overwriting_config(self, _master_key):
        config = {**self.config, "provider": "custom", "base_url": "https://models.example.com/v1"}
        row = UserApiConfig.objects.create(
            user=self.user, **config, api_key_cipher=encrypt_secret("saved-key")
        )
        with patch("agent.views.check_model_connection") as probe:
            for fields, expected in (
                ({}, "saved-key"),
                ({"api_key": "draft-key"}, "draft-key"),
                ({"clear_key": True}, None),
                ({"base_url": "https://other.example.com/v1"}, None),
            ):
                response = self.client.post(self.url, {**config, **fields}, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(probe.call_args.args[0].get("api_key"), expected)
        self.assertEqual(UserApiConfig.objects.get(pk=row.pk).api_key_cipher, row.api_key_cipher)

    def test_timeout_returns_actionable_message(self):
        with patch("agent.views.check_model_connection", side_effect=httpx.ReadTimeout("timeout")):
            response = self.client.post(self.url, self.config, format="json")
        self.assertEqual(response.status_code, 504)
        self.assertIn("超时", response.json()["detail"])
