from django.contrib.auth.models import User
from django.db import models


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