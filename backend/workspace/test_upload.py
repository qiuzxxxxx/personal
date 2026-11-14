"""Regression tests for phone (QR) upload sessions."""
from __future__ import annotations

import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import AccountSecurity
from workspace.models import Material, Task, TaskMaterial, UploadReceipt, UploadSession

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


class UploadSessionTestCase(APITestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="workspace-upload-test-")
        self.override = override_settings(
            MEDIA_ROOT=self.tempdir, PUBLIC_BASE_URL="https://workbench.example.com"
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.tempdir, True)

        self.owner = User.objects.create_user(username="owner", password="pw-owner-123456")
        self.other = User.objects.create_user(username="other", password="pw-other-123456")
        self.token = Token.objects.create(user=self.owner)
        self.other_token = Token.objects.create(user=self.other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def create_session(self, **payload):
        return self.client.post("/api/upload/sessions/", payload, format="json")

    def phone_client(self, upload_token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Upload {upload_token}")

    # -- session management ------------------------------------------------ #
    def test_create_session_returns_raw_token_once(self):
        response = self.create_session()
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["token"])
        self.assertTrue(payload["qr_payload"].startswith("https://workbench.example.com/upload#session="))
        self.assertIn(payload["token"], payload["qr_payload"])

        session = UploadSession.objects.get(pk=payload["id"])
        self.assertNotEqual(session.token_digest, payload["token"])
        self.assertEqual(len(session.token_digest), 64)

    def test_session_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.create_session().status_code, 401)

    def test_active_session_limit_revokes_oldest(self):
        for _ in range(4):
            self.create_session()
        self.assertEqual(
            UploadSession.objects.filter(owner=self.owner, state="active").count(), 3
        )

    def test_revoke_stops_uploads(self):
        session = self.create_session().json()
        revoked = self.client.post(f"/api/upload/sessions/{session['id']}/revoke/")
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.json()["state"], "revoked")

        self.phone_client(session["token"])
        prepare = self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "abc-1",
                "original_name": "photo.png",
                "declared_size": len(PNG_BYTES),
            },
            format="json",
        )
        self.assertEqual(prepare.status_code, 401)

    def test_status_lists_receipts(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "abc-2",
                "original_name": "photo.png",
                "declared_size": len(PNG_BYTES),
            },
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        status = self.client.get(f"/api/upload/sessions/{session['id']}/")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(len(status.json()["receipts"]), 1)

    def test_owner_cannot_read_other_session(self):
        session = self.create_session().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        self.assertEqual(self.client.get(f"/api/upload/sessions/{session['id']}/").status_code, 404)

    # -- upload flow ------------------------------------------------------- #
    def test_prepare_and_upload_commits_material(self):
        task = self.client.post("/api/tasks/", {"title": "合同照片"}, format="json").json()
        session = self.create_session(task=task["id"]).json()

        self.phone_client(session["token"])
        prepare = self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "upload-1",
                "original_name": "photo.png",
                "declared_size": len(PNG_BYTES),
            },
            format="json",
        )
        self.assertEqual(prepare.status_code, 201)
        receipt = prepare.json()
        self.assertEqual(receipt["state"], "reserved")

        content = self.client.post(
            f"/api/upload/phone/receipts/{receipt['id']}/content/",
            {"file": SimpleUploadedFile("photo.png", PNG_BYTES)},
            format="multipart",
        )
        self.assertEqual(content.status_code, 201)
        self.assertEqual(content.json()["state"], "committed")

        material = Material.objects.get(owner=self.owner)
        self.assertEqual(material.source, "qr")
        self.assertEqual(material.original_name, "photo.png")
        self.assertTrue(material.sha256)
        self.assertEqual(TaskMaterial.objects.filter(task_id=task["id"]).count(), 1)

    def test_prepare_is_idempotent(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        payload = {
            "client_upload_id": "same-id",
            "original_name": "photo.png",
            "declared_size": len(PNG_BYTES),
        }
        first = self.client.post("/api/upload/phone/receipts/", payload, format="json")
        second = self.client.post("/api/upload/phone/receipts/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(UploadReceipt.objects.count(), 1)

    def test_prepare_rejects_metadata_mismatch(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        base = {
            "client_upload_id": "same-id",
            "original_name": "photo.png",
            "declared_size": len(PNG_BYTES),
        }
        self.client.post("/api/upload/phone/receipts/", base, format="json")
        mismatch = self.client.post(
            "/api/upload/phone/receipts/",
            {**base, "original_name": "other.png"},
            format="json",
        )
        self.assertEqual(mismatch.status_code, 409)

    def test_prepare_rejects_unsupported_type(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        response = self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "exe-1",
                "original_name": "run.exe",
                "declared_size": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_quota_is_enforced(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        # Shrink the quota so the reservation must fail.
        UploadSession.objects.filter(pk=session["id"]).update(max_bytes=1)
        response = self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "too-big",
                "original_name": "photo.png",
                "declared_size": len(PNG_BYTES),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_upload_token_cannot_reach_owner_data(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        self.assertEqual(self.client.get("/api/tasks/").status_code, 401)
        self.assertEqual(self.client.get("/api/library/materials/").status_code, 401)

    def test_invalid_upload_token_is_rejected(self):
        self.phone_client("not-a-real-token")
        response = self.client.get("/api/upload/phone/session/")
        self.assertEqual(response.status_code, 401)

    def test_content_requires_the_matching_session(self):
        session = self.create_session().json()
        other_session = self.create_session().json()
        self.phone_client(session["token"])
        prepare = self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "cross-1",
                "original_name": "photo.png",
                "declared_size": len(PNG_BYTES),
            },
            format="json",
        ).json()
        self.phone_client(other_session["token"])
        response = self.client.get(f"/api/upload/phone/receipts/{prepare['id']}/")
        self.assertEqual(response.status_code, 404)

    def test_password_reset_invalidates_sessions(self):
        session = self.create_session().json()
        AccountSecurity.bump(self.owner)
        self.phone_client(session["token"])
        response = self.client.get("/api/upload/phone/session/")
        self.assertEqual(response.status_code, 403)

    def test_size_mismatch_is_rejected(self):
        session = self.create_session().json()
        self.phone_client(session["token"])
        prepare = self.client.post(
            "/api/upload/phone/receipts/",
            {
                "client_upload_id": "small-1",
                "original_name": "photo.png",
                "declared_size": 10,
            },
            format="json",
        ).json()
        response = self.client.post(
            f"/api/upload/phone/receipts/{prepare['id']}/content/",
            {"file": SimpleUploadedFile("photo.png", PNG_BYTES)},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(UploadReceipt.objects.get(pk=prepare["id"]).state, "failed")
