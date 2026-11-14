"""Small end-to-end smoke test against a running zixxx backend.

Usage:
    python smoke_test.py http://127.0.0.1:8000

It exercises auth, transfer visibility, chat history, agent attachments and the
streaming error path.  It cleans up files it creates through the admin API
where possible.  Do not run against a database whose data you care about.
"""
from __future__ import annotations

import io
import json
import os
import sys
import uuid

import httpx

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

from agent.crypto import decrypt_secret  # noqa: E402
from agent.models import UserApiConfig  # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api"
PASSWORDS = {
    username: os.environ[f"NEXUS_PASSWORD_{username.upper()}"]
    for username in ("qzx", "sqx", "yk")
}
checks: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{label} failed {detail}")
    checks.append(label)
    print(f"  OK  {label}")


def login(client: httpx.Client, username: str) -> dict:
    response = client.post(
        f"{API}/auth/login/",
        json={"username": username, "password": PASSWORDS[username]},
    )
    check(f"login {username}", response.status_code == 200, response.text)
    return response.json()


def main() -> None:
    # trust_env=False: never route localhost checks through a system proxy.
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        live = client.get(f"{API}/health/live/")
        check("health live", live.status_code == 200, live.text)
        ready = client.get(f"{API}/health/ready/")
        check("health ready", ready.status_code == 200, ready.text)

        qzx = login(client, "qzx")
        sqx = login(client, "sqx")
        check("qzx is super admin", qzx["user"]["is_super"])
        check("qzx is chat user", qzx["user"]["is_chat_user"])
        check("sqx is admin", sqx["user"]["is_admin"])
        check("sqx not super", not sqx["user"]["is_super"])
        check("sqx is chat user", sqx["user"]["is_chat_user"])

        qzx_headers = {"Authorization": f"Token {qzx['token']}"}
        sqx_headers = {"Authorization": f"Token {sqx['token']}"}

        public = client.post(
            f"{API}/transfer/files/",
            data={"is_public": "true", "remark": "smoke public", "uploader_name": "测试访客"},
            files={"file": ("hello.txt", b"hello zixxx", "text/plain")},
        )
        check("anon public upload", public.status_code == 201, public.text)
        public_id = public.json()["id"]

        private = client.post(
            f"{API}/transfer/files/",
            data={"is_public": "false", "remark": "smoke private"},
            files={"file": ("secret.txt", b"top secret", "text/plain")},
        )
        check("anon private upload", private.status_code == 201, private.text)
        private_id = private.json()["id"]

        anon_list = client.get(f"{API}/transfer/files/")
        anon_ids = {item["id"] for item in anon_list.json()}
        check("anon sees public", public_id in anon_ids)
        check("anon cannot see private", private_id not in anon_ids)

        anon_download = client.get(
            f"{API}/transfer/files/{public_id}/download/"
        )
        check("anon download public", anon_download.status_code == 200)
        denied = client.get(f"{API}/transfer/files/{private_id}/download/")
        check("anon private download denied", denied.status_code == 403)

        forbidden = client.patch(
            f"{API}/transfer/files/{private_id}/", json={"is_public": True}
        )
        check("anon cannot patch", forbidden.status_code in (401, 403))

        admin_list = client.get(f"{API}/transfer/files/", headers=qzx_headers)
        admin_ids = {item["id"] for item in admin_list.json()}
        check("qzx sees all", public_id in admin_ids and private_id in admin_ids)

        downloaded = client.get(
            f"{API}/transfer/files/{private_id}/download/", headers=qzx_headers
        )
        check("qzx downloads private", downloaded.status_code == 200)
        check("private bytes intact", downloaded.content == b"top secret")

        patched = client.patch(
            f"{API}/transfer/files/{private_id}/",
            headers=qzx_headers,
            json={"original_name": "renamed-secret.txt", "is_public": True, "remark": "now public"},
        )
        check("qzx patch", patched.status_code == 200, patched.text)
        check("renamed", patched.json()["original_name"] == "renamed-secret.txt")
        check("visibility toggled", patched.json()["is_public"] is True)

        now_visible = client.get(f"{API}/transfer/files/")
        check(
            "visibility switch visible to anon",
            private_id in {item["id"] for item in now_visible.json()},
        )

        for file_id in (public_id, private_id):
            deleted = client.delete(
                f"{API}/transfer/files/{file_id}/", headers=qzx_headers
            )
            check(f"delete {file_id[:8]}", deleted.status_code == 204)

        # ---- guest account yk: upload & browse own/public, never manage ----
        yk = login(client, "yk")
        yk_headers = {"Authorization": f"Token {yk['token']}"}
        check("yk is not admin", not yk["user"]["is_admin"])
        check("yk role label", yk["user"]["role"].startswith("游客"))
        check("yk is not chat user", not yk["user"]["is_chat_user"])

        yk_private = client.post(
            f"{API}/transfer/files/",
            headers=yk_headers,
            data={"is_public": "false", "remark": "yk own"},
            files={"file": ("yk-note.txt", b"yk private", "text/plain")},
        )
        check("yk private upload", yk_private.status_code == 201, yk_private.text)
        yk_private_id = yk_private.json()["id"]
        check("yk upload attributed", yk_private.json()["uploader_name"] == "yk")

        spoof = client.post(
            f"{API}/transfer/files/",
            data={"is_public": "true", "uploader_name": "qzx"},
            files={"file": ("spoof.txt", b"spoof", "text/plain")},
        )
        check("anon uploader name sanitized", spoof.json()["uploader_name"] == "免密访客")
        spoof_id = spoof.json()["id"]

        anon_list = client.get(f"{API}/transfer/files/")
        anon_ids = {item["id"] for item in anon_list.json()}
        check("anon cannot see yk private", yk_private_id not in anon_ids)

        yk_list = client.get(f"{API}/transfer/files/", headers=yk_headers)
        yk_ids = {item["id"] for item in yk_list.json()}
        check("yk sees own private", yk_private_id in yk_ids)
        check("yk sees public", spoof_id in yk_ids)

        yk_dl = client.get(
            f"{API}/transfer/files/{yk_private_id}/download/", headers=yk_headers
        )
        check("yk downloads own private", yk_dl.status_code == 200)
        anon_dl = client.get(f"{API}/transfer/files/{yk_private_id}/download/")
        check("anon yk-private download denied", anon_dl.status_code == 403)

        yk_patch = client.patch(
            f"{API}/transfer/files/{yk_private_id}/",
            headers=yk_headers,
            json={"is_public": True},
        )
        check("yk cannot patch", yk_patch.status_code == 403)
        yk_del = client.delete(
            f"{API}/transfer/files/{yk_private_id}/", headers=yk_headers
        )
        check("yk cannot delete", yk_del.status_code == 403)

        for fid in (yk_private_id, spoof_id):
            deleted = client.delete(f"{API}/transfer/files/{fid}/", headers=qzx_headers)
            check(f"qzx cleans {fid[:8]}", deleted.status_code == 204)

        # ---- agent access: login required, guest excluded ----
        anon_conv = client.get(f"{API}/agent/conversations/")
        check("anonymous agent denied", anon_conv.status_code in (401, 403))
        yk_conv = client.get(f"{API}/agent/conversations/", headers=yk_headers)
        check("yk agent list denied", yk_conv.status_code == 403)
        yk_chat = client.post(
            f"{API}/agent/chat/",
            headers=yk_headers,
            json={
                "message": "hi",
                "api_config": {
                    "provider": "custom",
                    "base_url": "http://127.0.0.1:9/v1",
                    "model": "m",
                },
            },
        )
        check("yk agent chat denied", yk_chat.status_code == 403)

        # ---- account admin: qzx / sqx reset passwords & read others' logs ----
        check("qzx is admin flag", qzx["user"]["is_admin"])
        check("yk not admin flag", not yk["user"]["is_admin"])

        users_list = client.get(f"{API}/auth/users/", headers=sqx_headers)
        check("admin lists accounts", users_list.status_code == 200)
        users_denied = client.get(f"{API}/auth/users/", headers=yk_headers)
        check("yk cannot list accounts", users_denied.status_code == 403)

        new_pwd = "fresh-pass-456"
        pwd_change = client.post(
            f"{API}/auth/yk/password/",
            headers=sqx_headers,
            json={"new_password": new_pwd},
        )
        check("sqx resets yk password", pwd_change.status_code == 200, pwd_change.text)

        old_token = yk_headers["Authorization"]
        revoked = client.get(f"{API}/auth/me/", headers={"Authorization": old_token})
        check("password reset revokes old token", revoked.status_code == 401)
        old_yk_login = client.post(
            f"{API}/auth/login/", json={"username": "yk", "password": PASSWORDS["yk"]}
        )
        check("old yk password rejected", old_yk_login.status_code == 401)
        yk2 = client.post(
            f"{API}/auth/login/", json={"username": "yk", "password": new_pwd}
        )
        check("new yk password works", yk2.status_code == 200)
        yk_headers = {"Authorization": f"Token {yk2.json()['token']}"}

        self_change = client.post(
            f"{API}/auth/qzx/password/",
            headers=qzx_headers,
            json={"new_password": "whatever-123"},
        )
        check("admin cannot reset own via this api", self_change.status_code == 400)

        own_logs = client.get(f"{API}/auth/logs/", headers=yk_headers)
        check("user sees own logs", own_logs.status_code == 200)
        check(
            "own logs include login",
            any(item["action"] == "login" for item in own_logs.json()),
        )
        other_logs = client.get(f"{API}/auth/logs/?username=qzx", headers=yk_headers)
        check("yk cannot read others logs", other_logs.status_code == 403)
        admin_logs = client.get(f"{API}/auth/logs/?username=yk", headers=sqx_headers)
        check("admin reads other logs", admin_logs.status_code == 200)
        check(
            "admin sees password_changed log",
            any(item["action"] == "password_changed" for item in admin_logs.json()),
        )

        non_admin_change = client.post(
            f"{API}/auth/yk/password/",
            headers=yk_headers,
            json={"new_password": "nope-123456"},
        )
        check("non-admin cannot change passwords", non_admin_change.status_code == 403)

        # ---- admin tiers: sqx (admin) vs qzx (super) ----
        sqx_pwd_yk = client.post(
            f"{API}/auth/yk/password/",
            headers=sqx_headers,
            json={"new_password": "sqx-set-pass-1"},
        )
        check("sqx resets yk password again", sqx_pwd_yk.status_code == 200)
        restore_yk = client.post(
            f"{API}/auth/yk/password/",
            headers=qzx_headers,
            json={"new_password": PASSWORDS["yk"]},
        )
        check("super restores yk password", restore_yk.status_code == 200)
        yk3 = login(client, "yk")
        yk_headers = {"Authorization": f"Token {yk3['token']}"}

        sqx_pwd_qzx = client.post(
            f"{API}/auth/qzx/password/",
            headers=sqx_headers,
            json={"new_password": "nope-123456"},
        )
        check("sqx cannot reset super password", sqx_pwd_qzx.status_code == 403)

        sqx_logs_qzx = client.get(f"{API}/auth/logs/?username=qzx", headers=sqx_headers)
        check("sqx cannot read super logs", sqx_logs_qzx.status_code == 403)
        sqx_logs_yk = client.get(f"{API}/auth/logs/?username=yk", headers=sqx_headers)
        check("sqx reads regular logs", sqx_logs_yk.status_code == 200)
        qzx_logs_sqx = client.get(f"{API}/auth/logs/?username=sqx", headers=qzx_headers)
        check("super reads admin logs", qzx_logs_sqx.status_code == 200)

        priv = client.post(
            f"{API}/transfer/files/",
            data={"is_public": "false"},
            files={"file": ("tier-private.txt", b"tier", "text/plain")},
        )
        check("tier private upload", priv.status_code == 201, priv.text)
        priv_id = priv.json()["id"]
        sqx_patch = client.patch(
            f"{API}/transfer/files/{priv_id}/",
            headers=sqx_headers,
            json={"remark": "nope"},
        )
        check("sqx cannot manage transfer station", sqx_patch.status_code == 403)
        qzx_patch = client.patch(
            f"{API}/transfer/files/{priv_id}/",
            headers=qzx_headers,
            json={"is_public": True},
        )
        check("qzx manages transfer station", qzx_patch.status_code == 200, qzx_patch.text)
        tier_del = client.delete(f"{API}/transfer/files/{priv_id}/", headers=qzx_headers)
        check("qzx deletes transfer file", tier_del.status_code == 204)

        # ---- server-side encrypted API config (disposable account only) ----
        from django.contrib.auth.models import User as DjUser
        from rest_framework.authtoken.models import Token

        smoke_user, _ = DjUser.objects.get_or_create(username="smoke_agent")
        smoke_user.set_password("smoke-pass-123")
        smoke_user.save()
        smoke_token, _ = Token.objects.get_or_create(user=smoke_user)
        sm_headers = {"Authorization": f"Token {smoke_token.key}"}

        secret = "sk-super-secret-abcdef123456"
        put_cfg = client.put(
            f"{API}/agent/config/",
            headers=sm_headers,
            json={
                "provider": "custom",
                "base_url": "http://127.0.0.1:9/v1",
                "model": "smoke-model",
                "system_prompt": "smoke",
                "api_key": secret,
            },
        )
        check("save config", put_cfg.status_code == 200, put_cfg.text)
        check("config reports has_key", put_cfg.json()["has_key"] is True)
        check("save response has no plaintext", secret not in put_cfg.text)
        get_cfg = client.get(f"{API}/agent/config/", headers=sm_headers)
        check("config get masked", secret not in get_cfg.text)
        check("config key hint", get_cfg.json()["key_hint"].endswith("3456"))
        yk_cfg = client.put(
            f"{API}/agent/config/",
            headers=yk_headers,
            json={
                "provider": "custom",
                "base_url": "http://127.0.0.1:9/v1",
                "model": "m",
            },
        )
        check("yk config denied", yk_cfg.status_code == 403)

        saved_stream = client.post(
            f"{API}/agent/chat/",
            headers=sm_headers,
            json={"message": "use saved key", "api_config": {"use_saved": True}},
        )
        check(
            "chat accepts saved-key config",
            saved_stream.status_code == 200,
            saved_stream.text[:300],
        )

        row = UserApiConfig.objects.get(user__username="smoke_agent")
        check("key encrypted at rest", secret not in row.api_key_cipher)
        check("key decryptable server-side", decrypt_secret(row.api_key_cipher) == secret)

        if os.environ.get("SMOKE_INCLUDE_CHAT") == "1":
            chat_list = client.get(f"{API}/chat/messages/", headers=qzx_headers)
            check("chat history", chat_list.status_code == 200)
            chat_post = client.post(
                f"{API}/chat/messages/",
                headers=qzx_headers,
                json={"content": f"smoke-{uuid.uuid4().hex[:8]}"},
            )
            check("chat text send", chat_post.status_code == 201, chat_post.text)
            chat_upload = client.post(
                f"{API}/chat/files/",
                headers=qzx_headers,
                files={"file": ("note.txt", b"chat attachment", "text/plain")},
            )
            check("chat file send", chat_upload.status_code == 201, chat_upload.text)
            chat_file_url = chat_upload.json()["file_url"]
            chat_download = client.get(f"{BASE}{chat_file_url}", headers=qzx_headers)
            check("chat file download", chat_download.status_code == 200)
            yk_chat_api = client.get(f"{API}/chat/messages/", headers=yk_headers)
            check("yk chat denied", yk_chat_api.status_code == 403)

        agent_headers = sm_headers
        conversations = client.get(
            f"{API}/agent/conversations/", headers=agent_headers
        )
        check("agent conversation list", conversations.status_code == 200)
        attachment = client.post(
            f"{API}/agent/attachments/",
            headers=agent_headers,
            files={"file": ("notes.md", b"# Title\n\nzixxx attachment body", "text/markdown")},
        )
        check("agent attachment upload", attachment.status_code == 201, attachment.text)
        attachment_id = attachment.json()["id"]

        stream = client.post(
            f"{API}/agent/chat/",
            headers=agent_headers,
            json={
                "message": "Summarize the attachment briefly.",
                "attachment_ids": [attachment_id],
                "api_config": {
                    "provider": "custom",
                    "base_url": "http://127.0.0.1:9/v1",
                    "api_key": "test-not-real",
                    "model": "smoke-model",
                },
            },
        )
        check("agent stream accepts", stream.status_code == 200, stream.text[:500])
        check("agent stream SSE", "text/event-stream" in stream.headers.get("content-type", ""))
        events = [
            json.loads(line[6:])
            for line in stream.text.splitlines()
            if line.startswith("data: ")
        ]
        check("agent stream meta", any(event["type"] == "meta" for event in events))
        check(
            "agent stream safe error",
            any(event["type"] == "error" for event in events),
        )
        conversation_id = next(
            event["conversation_id"] for event in events if event["type"] == "meta"
        )
        persisted = client.get(
            f"{API}/agent/conversations/{conversation_id}/", headers=agent_headers
        )
        check("agent conversation persisted", persisted.status_code == 200)
        check("agent user message persisted", len(persisted.json()["messages"]) == 1)
        client.delete(
            f"{API}/agent/conversations/{conversation_id}/", headers=agent_headers
        )

        smoke_user.delete()
        check(
            "disposable account cleaned",
            not UserApiConfig.objects.filter(user__username="smoke_agent").exists(),
        )

        restore = client.post(
            f"{API}/auth/yk/password/",
            headers=qzx_headers,
            json={"new_password": PASSWORDS["yk"]},
        )
        check("restore yk password", restore.status_code == 200)

    print(f"\n{len(checks)} checks passed.")


if __name__ == "__main__":
    main()
