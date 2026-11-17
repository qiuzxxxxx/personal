"""Regression tests for the private material library."""
from __future__ import annotations

import io
import zipfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from config.testing import remove_scratch, scratch_dir
from workspace.models import Folder, Material, Task, TaskMaterial

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF_BYTES = b"%PDF-1.7\n" + b"\x00" * 64


class LibraryTestCase(APITestCase):
    def setUp(self):
        self.tempdir = scratch_dir("workspace-library-test-")
        self.override = override_settings(MEDIA_ROOT=self.tempdir)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(remove_scratch, self.tempdir)

        self.owner = User.objects.create_user(username="owner", password="pw-owner-123456")
        self.other = User.objects.create_user(username="other", password="pw-other-123456")
        self.owner_token = Token.objects.create(user=self.owner)
        self.other_token = Token.objects.create(user=self.other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

    def upload(self, name="note.txt", content=b"hello world", **extra):
        payload = {"file": SimpleUploadedFile(name, content)}
        payload.update(extra)
        return self.client.post("/api/library/materials/", payload, format="multipart")

    def test_openxml_office_upload_is_accepted(self):
        """A .docx is a zip container and must not be rejected as a mismatch."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "<document/>")
        response = self.upload("report.docx", buffer.getvalue())
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["extension"], "docx")

    def test_mismatched_content_is_rejected(self):
        response = self.upload("payload.zip", PNG_BYTES)
        self.assertEqual(response.status_code, 400)

    # -- folders ---------------------------------------------------------- #
    def test_folder_lifecycle(self):
        created = self.client.post("/api/library/folders/", {"name": "合同"}, format="json")
        self.assertEqual(created.status_code, 201)
        folder_id = created.json()["id"]

        renamed = self.client.patch(
            f"/api/library/folders/{folder_id}/",
            {"name": "合同 2026", "version": created.json()["version"]},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "合同 2026")

        deleted = self.client.delete(f"/api/library/folders/{folder_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/library/folders/").json()["count"], 0)

    # -- materials -------------------------------------------------------- #
    def test_upload_and_download(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        material = response.json()
        self.assertEqual(material["original_name"], "note.txt")
        self.assertEqual(material["size_bytes"], len(b"hello world"))
        self.assertTrue(material["sha256"])
        self.assertTrue(material["download_url"].endswith("/download/"))

        download = self.client.get(material["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"hello world")

    def test_storage_name_is_server_generated(self):
        response = self.upload(name="重要 合同.png", content=PNG_BYTES)
        self.assertEqual(response.status_code, 201)
        material = Material.objects.get(pk=response.json()["id"])
        self.assertNotIn("重要", material.storage_key.name)
        self.assertTrue(material.storage_key.name.endswith(".png"))
        self.assertTrue(material.storage_key.name.startswith("library/"))

    def test_rejects_unsupported_extension(self):
        response = self.upload(name="payload.exe", content=b"MZ\x90\x00")
        self.assertEqual(response.status_code, 400)

    def test_rejects_content_extension_mismatch(self):
        response = self.upload(name="photo.png", content=b"this is plain text")
        self.assertEqual(response.status_code, 400)

    def test_rejects_empty_file(self):
        response = self.upload(content=b"")
        self.assertEqual(response.status_code, 400)

    def test_owner_isolation_on_download(self):
        created = self.upload().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        self.assertEqual(self.client.get(created["download_url"]).status_code, 404)
        self.assertEqual(self.client.get("/api/library/materials/").json()["count"], 0)

    def test_requires_authentication(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/library/materials/").status_code, 401)

    def test_soft_delete_and_restore(self):
        created = self.upload().json()
        deleted = self.client.delete(f"/api/library/materials/{created['id']}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/library/materials/").json()["count"], 0)
        self.assertEqual(
            self.client.get("/api/library/materials/?deleted=true").json()["count"], 1
        )
        self.assertEqual(self.client.get(created["download_url"]).status_code, 404)

        restored = self.client.post(f"/api/library/materials/{created['id']}/restore/")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(self.client.get("/api/library/materials/").json()["count"], 1)

    def test_filter_by_folder(self):
        folder = self.client.post("/api/library/folders/", {"name": "合同"}, format="json").json()
        self.upload()
        self.upload(name="other.txt", content=b"other", folder=folder["id"])
        payload = self.client.get(f"/api/library/materials/?folder={folder['id']}").json()
        self.assertEqual(payload["count"], 1)

    # -- task attachments ------------------------------------------------- #
    def test_task_material_link(self):
        task = self.client.post("/api/tasks/", {"title": "签署合同"}, format="json").json()
        material = self.upload().json()

        linked = self.client.post(
            f"/api/tasks/{task['id']}/materials/", {"material": material["id"]}, format="json"
        )
        self.assertEqual(linked.status_code, 201)
        self.assertEqual(TaskMaterial.objects.count(), 1)

        listed = self.client.get(f"/api/tasks/{task['id']}/materials/").json()
        self.assertEqual(len(listed), 1)

        removed = self.client.delete(
            f"/api/tasks/{task['id']}/materials/{material['id']}/"
        )
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(TaskMaterial.objects.count(), 0)

    def test_task_material_rejects_foreign_material(self):
        task = self.client.post("/api/tasks/", {"title": "任务"}, format="json").json()
        material = self.upload().json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.post(
            f"/api/tasks/{task['id']}/materials/", {"material": material["id"]}, format="json"
        )
        self.assertEqual(response.status_code, 404)
