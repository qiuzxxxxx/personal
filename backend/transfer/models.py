import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TransferFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to="transfer_station/%Y/%m/")
    original_name = models.CharField(max_length=255, verbose_name="文件名")
    file_size = models.BigIntegerField(default=0, verbose_name="文件大小(字节)")
    file_type = models.CharField(max_length=100, blank=True, verbose_name="MIME类型")
    remark = models.CharField(
        max_length=255, blank=True, default="", verbose_name="备注说明"
    )
    is_public = models.BooleanField(default=True, verbose_name="是否对所有人可见")
    visible_until = models.DateTimeField(null=True, blank=True, verbose_name="可见截止时间")
    uploader_name = models.CharField(
        max_length=64, default="免密访客", verbose_name="上传者标识"
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_public", "-created_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.original_name


class TransferAnnouncement(models.Model):
    content = models.TextField(blank=True, default="")
    login_content = models.TextField(blank=True, default="")
    login_updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="transfer_announcements",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class AnnouncementHistory(models.Model):
    """Past announcements, newest first, for the public history view."""

    KIND_TRANSFER = "transfer"
    KIND_LOGIN = "login"
    KIND_CHOICES = [
        (KIND_TRANSFER, "中转站公告"),
        (KIND_LOGIN, "登录页公告"),
    ]

    kind = models.CharField(max_length=16, choices=KIND_CHOICES, db_index=True)
    content = models.TextField()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="announcement_history",
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "公告历史"
        verbose_name_plural = "公告历史"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.kind}@{self.created_at:%Y-%m-%d %H:%M}"
