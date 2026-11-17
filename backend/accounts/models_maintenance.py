from django.db import models


class SiteMaintenance(models.Model):
    """全局维护模式开关：开启后除最高管理员外所有账号无法登录。"""

    enabled = models.BooleanField(default=False, db_index=True)
    reason = models.TextField(blank=True, default="", max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def load(cls) -> "SiteMaintenance":
        """Return the single site-wide maintenance row, creating it if needed."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def __str__(self) -> str:  # pragma: no cover
        return f"maintenance: {'ON' if self.enabled else 'OFF'}"


class AccountLock(models.Model):
    """账号锁定：被锁定的账号无法登录，仅超级管理员可解锁。"""

    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="account_lock"
    )
    locked = models.BooleanField(default=False, db_index=True)
    reason = models.CharField(max_length=255, blank=True, default="")
    locked_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="locked_accounts",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "账号锁定"
        verbose_name_plural = "账号锁定"

    def __str__(self) -> str:  # pragma: no cover
        return f"lock:{self.user.username} locked={self.locked}"
