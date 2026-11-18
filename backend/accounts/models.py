from django.contrib.auth.models import User
from django.db import models

from .models_maintenance import AccountLock, SiteMaintenance  # noqa: F401


class SiteAbout(models.Model):
    """Singleton content of the public "about" page.

    Every field is editable by the highest administrator; readers get the
    page without authentication. Empty fields are simply hidden on the page.
    """

    site_name = models.CharField(max_length=100, blank=True, default="缺页中断")
    tagline = models.CharField(max_length=200, blank=True, default="")
    intro = models.TextField(max_length=5000, blank=True, default="")
    features = models.TextField(max_length=5000, blank=True, default="")
    developer = models.CharField(max_length=200, blank=True, default="")
    contact = models.CharField(max_length=500, blank=True, default="")
    app_version = models.CharField(max_length=100, blank=True, default="")
    guide = models.TextField(max_length=5000, blank=True, default="")
    links = models.JSONField(default=list, blank=True)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="site_about_updates"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "关于页面"
        verbose_name_plural = "关于页面"

    @classmethod
    def load(cls) -> "SiteAbout":
        return cls.objects.get_or_create(pk=1)[0]


class AccountProfile(models.Model):
    """Account-level access selected by the highest administrator."""

    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"
    ACCESS_CHOICES = [
        (ADMIN, "管理员"),
        (MEMBER, "成员"),
        (GUEST, "访客"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="account_profile"
    )
    access_level = models.CharField(
        max_length=16, choices=ACCESS_CHOICES, default=MEMBER, db_index=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.username}:{self.access_level}"


class AccountSecurity(models.Model):
    """Security state that invalidates delivery credentials when it changes."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="security"
    )
    auth_version = models.PositiveIntegerField(default=0)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"security:{self.user.username}@{self.auth_version}"

    @classmethod
    def version_for(cls, user) -> int:
        state, _ = cls.objects.get_or_create(user=user)
        return state.auth_version

    @classmethod
    def bump(cls, user) -> int:
        state, _ = cls.objects.get_or_create(user=user)
        state.auth_version += 1
        state.save(update_fields=["auth_version", "updated_at"])
        return state.auth_version


class ActivityLog(models.Model):
    """Security/operation audit trail.

    ``user`` is the account the event belongs to, ``actor`` is whoever
    triggered it (differs from ``user`` for admin actions such as password
    resets). Only account admins (zx / qzx) may read other users' logs.
    """

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
    )
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acted_logs",
    )
    action = models.CharField(max_length=48, db_index=True)
    detail = models.CharField(max_length=255, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"

    def __str__(self) -> str:  # pragma: no cover
        who = self.user.username if self.user else "anonymous"
        return f"{who} {self.action} @{self.created_at:%m-%d %H:%M}"
