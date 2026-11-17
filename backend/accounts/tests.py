from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import AccountLock, AccountProfile, SiteMaintenance


class AccountManagementTests(TestCase):
    def setUp(self):
        self.qzx = User.objects.create_user(
            "qzx", password="qzx-test-password-4821"
        )
        self.admin = User.objects.create_user(
            "admin-user", password="admin-test-password-4821"
        )
        AccountProfile.objects.create(
            user=self.admin, access_level=AccountProfile.ADMIN
        )
        self.client = APIClient()

    def test_new_login_revokes_previous_token(self):
        first = self.client.post(
            reverse("auth-login"),
            {"username": "qzx", "password": "qzx-test-password-4821"},
        )
        self.assertEqual(first.status_code, 200)
        first_token = first.json()["token"]

        second = self.client.post(
            reverse("auth-login"),
            {"username": "qzx", "password": "qzx-test-password-4821"},
        )
        self.assertEqual(second.status_code, 200)
        second_token = second.json()["token"]
        self.assertNotEqual(first_token, second_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {first_token}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {second_token}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

    def test_qzx_can_create_change_access_and_delete_account(self):
        self.client.force_authenticate(self.qzx)
        created = self.client.post(
            reverse("auth-user-create"),
            {
                "username": "New.Member",
                "password": "A-long-random-password-4821!",
                "access_level": "member",
            },
        )
        self.assertEqual(created.status_code, 201, created.json())
        user = User.objects.get(username="new.member")
        self.assertEqual(user.account_profile.access_level, AccountProfile.MEMBER)

        changed = self.client.patch(
            reverse("auth-user-detail", args=[user.username]),
            {"access_level": "guest"},
        )
        self.assertEqual(changed.status_code, 200)
        user.account_profile.refresh_from_db()
        self.assertEqual(user.account_profile.access_level, AccountProfile.GUEST)

        deleted = self.client.delete(
            reverse("auth-user-detail", args=[user.username])
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_regular_admin_cannot_create_delete_or_change_access(self):
        target = User.objects.create_user("member-user")
        AccountProfile.objects.create(
            user=target, access_level=AccountProfile.MEMBER
        )
        self.client.force_authenticate(self.admin)
        payload = {
            "username": "blocked-user",
            "password": "A-long-random-password-4821!",
            "access_level": "member",
        }
        self.assertEqual(
            self.client.post(reverse("auth-user-create"), payload).status_code,
            403,
        )
        detail = reverse("auth-user-detail", args=[target.username])
        self.assertEqual(
            self.client.patch(detail, {"access_level": "admin"}).status_code,
            403,
        )
        self.assertEqual(self.client.delete(detail).status_code, 403)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())

    def test_guest_role_is_blocked_from_workspace_api(self):
        guest = User.objects.create_user("visitor-user")
        AccountProfile.objects.create(
            user=guest, access_level=AccountProfile.GUEST
        )
        self.client.force_authenticate(guest)
        self.assertEqual(
            self.client.get(reverse("workspace-today")).status_code,
            403,
        )


class MaintenanceAndLockTests(TestCase):
    def setUp(self):
        self.qzx = User.objects.create_user(
            "qzx", password="qzx-test-password-4821"
        )
        self.member = User.objects.create_user(
            "member-user", password="member-test-password-4821"
        )
        self.admin = User.objects.create_user(
            "admin-user", password="admin-test-password-4821"
        )
        AccountProfile.objects.create(
            user=self.admin, access_level=AccountProfile.ADMIN
        )
        self.client = APIClient()

    def login(self, username, password):
        return self.client.post(
            reverse("auth-login"), {"username": username, "password": password}
        )

    def test_maintenance_blocks_members_and_revokes_existing_sessions(self):
        member_login = self.login("member-user", "member-test-password-4821")
        self.assertEqual(member_login.status_code, 200)
        member_token = member_login.json()["token"]

        self.client.force_authenticate(self.qzx)
        toggled = self.client.post(
            reverse("maintenance-toggle"),
            {"enabled": True, "reason": "数据库升级"},
        )
        self.assertEqual(toggled.status_code, 200, toggled.json())
        self.assertTrue(SiteMaintenance.load().enabled)

        status = self.client.get(reverse("maintenance-status"))
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["enabled"])
        self.assertEqual(status.json()["reason"], "数据库升级")

        # 已有成员会话在开启维护时被立即失效。
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {member_token}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)
        # 登录页即使带着已失效 Token，也必须能读到维护状态。
        self.assertEqual(
            self.client.get(reverse("maintenance-status")).status_code, 200
        )
        self.client.credentials()

        blocked = self.login("member-user", "member-test-password-4821")
        self.assertEqual(blocked.status_code, 503)
        self.assertIn("数据库升级", blocked.json()["detail"])

        allowed = self.login("qzx", "qzx-test-password-4821")
        self.assertEqual(allowed.status_code, 200, allowed.json())

    def test_locked_account_is_rejected_and_unlock_restores_login(self):
        member_login = self.login("member-user", "member-test-password-4821")
        self.assertEqual(member_login.status_code, 200)
        member_token = member_login.json()["token"]

        self.client.force_authenticate(self.qzx)
        locked = self.client.post(
            reverse("account-lock-toggle"),
            {"username": "MEMBER-USER", "locked": True, "reason": "违规操作"},
        )
        self.assertEqual(locked.status_code, 200, locked.json())
        lock = AccountLock.objects.get(user=self.member)
        self.assertTrue(lock.locked)

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {member_token}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)
        self.client.credentials()

        blocked = self.login("member-user", "member-test-password-4821")
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("违规操作", blocked.json()["detail"])

        self.client.force_authenticate(self.qzx)
        rows = self.client.get(reverse("account-lock-list")).json()
        self.assertEqual([row["username"] for row in rows], ["member-user"])
        self.assertEqual(rows[0]["locked_by"], "qzx")

        unlocked = self.client.post(
            reverse("account-lock-toggle"),
            {"username": "member-user", "locked": False, "reason": ""},
        )
        self.assertEqual(unlocked.status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.login("member-user", "member-test-password-4821").status_code, 200
        )

    def test_only_super_admin_can_manage_maintenance_and_locks(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post(
                reverse("maintenance-toggle"),
                {"enabled": True, "reason": ""},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("account-lock-list")).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                reverse("account-lock-toggle"),
                {"username": "member-user", "locked": True, "reason": ""},
            ).status_code,
            403,
        )
        self.assertFalse(SiteMaintenance.load().enabled)

    def test_super_admin_cannot_be_locked(self):
        self.client.force_authenticate(self.qzx)
        response = self.client.post(
            reverse("account-lock-toggle"),
            {"username": "qzx", "locked": True, "reason": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AccountLock.objects.filter(user=self.qzx).exists())
