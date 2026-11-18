"""Personal workspace models: projects, tasks, tags and daily entries.

Every record is owner scoped. The owner is taken from the request token and is
never accepted from client payloads.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from config.models import VersionedModel

TASK_STATUS = [
    ("todo", "待办"),
    ("doing", "进行中"),
    ("done", "已完成"),
    ("cancelled", "已取消"),
]

TASK_PRIORITY = [
    ("low", "低"),
    ("normal", "普通"),
    ("high", "高"),
]

PROJECT_STATUS = [
    ("active", "进行中"),
    ("archived", "已归档"),
]

OPEN_TASK_STATUSES = ("todo", "doing")


def normalize_tag_name(name: str) -> str:
    return " ".join(str(name or "").strip().split()).casefold()


class WorkspacePreference(models.Model):
    """Per account workspace settings."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_preference",
    )
    timezone = models.CharField(max_length=64, default="Asia/Shanghai")
    week_starts_on = models.PositiveSmallIntegerField(default=1)
    default_task_priority = models.CharField(max_length=16, default="normal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"preference:{self.user_id}"


class Project(VersionedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=10000, blank=True, default="")
    status = models.CharField(max_length=16, choices=PROJECT_STATUS, default="active")
    color = models.CharField(max_length=32, blank=True, default="")
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position", "created_at"]
        indexes = [models.Index(fields=["owner", "deleted_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Tag(VersionedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
    )
    name = models.CharField(max_length=64)
    normalized_name = models.CharField(max_length=64)
    color = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        ordering = ["normalized_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "normalized_name"],
                name="workspace_tag_owner_normalized_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Task(VersionedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=20000, blank=True, default="")
    status = models.CharField(max_length=16, choices=TASK_STATUS, default="todo")
    priority = models.CharField(max_length=16, choices=TASK_PRIORITY, default="normal")
    scheduled_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(default=45)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    position = models.IntegerField(default=0)
    client_request_id = models.CharField(max_length=64, blank=True, default="")
    tags = models.ManyToManyField(Tag, related_name="tasks", blank=True)

    class Meta:
        ordering = ["position", "created_at"]
        indexes = [
            models.Index(fields=["owner", "deleted_at", "scheduled_date"]),
            models.Index(fields=["owner", "deleted_at", "status"]),
            models.Index(fields=["owner", "due_at"]),
            models.Index(fields=["owner", "completed_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "client_request_id"],
                condition=~Q(client_request_id=""),
                name="workspace_task_owner_client_request_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title


class CalendarBlock(VersionedModel):
    """A single-day scheduled time block on the personal timeline."""

    BLOCK_TYPES = [
        ("task", "任务排期"),
        ("study", "学习复习"),
        ("habit", "每日例行"),
    ]
    ORIGIN_CHOICES = [
        ("manual", "手动创建"),
        ("backfill", "历史回填"),
    ]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_blocks",
    )
    task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="calendar_blocks",
    )
    title = models.CharField(max_length=200)
    block_type = models.CharField(max_length=16, choices=BLOCK_TYPES, default="task")
    origin = models.CharField(max_length=16, choices=ORIGIN_CHOICES, default="manual")
    day_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["day_date", "start_time", "created_at"]
        indexes = [
            models.Index(fields=["owner", "deleted_at", "day_date"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.day_date} {self.start_time:%H:%M} {self.title}"

    def clean(self) -> None:
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError(
                {"end_time": "结束时间必须晚于开始时间（不支持跨日时间块）。"}
            )

    def save(self, *args, **kwargs):
        if self.start_time and self.end_time and self.end_time > self.start_time:
            started = datetime.combine(date.min, self.start_time)
            ended = datetime.combine(date.min, self.end_time)
            self.duration_minutes = max(
                1, int((ended - started).total_seconds() // 60)
            )
        super().save(*args, **kwargs)


class FocusSession(models.Model):
    """Append-only focus log used for weekly statistics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="focus_sessions",
    )
    task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="focus_sessions",
    )
    target_title = models.CharField(max_length=200)
    minutes = models.PositiveIntegerField(default=25)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"focus:{self.owner_id}:{self.minutes}m"


class Folder(VersionedModel):
    """Single level folder inside the private material library."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_folders",
    )
    name = models.CharField(max_length=120)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position", "created_at"]
        indexes = [models.Index(fields=["owner", "deleted_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Material(VersionedModel):
    """A private file stored for the owner."""

    SOURCE_CHOICES = [
        ("desktop", "电脑上传"),
        ("qr", "手机扫码"),
        ("transfer_copy", "中转站副本"),
    ]
    STATE_CHOICES = [
        ("pending", "接收中"),
        ("ready", "可用"),
        ("failed", "失败"),
        ("deleting", "待永久删除"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    folder = models.ForeignKey(
        Folder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="materials",
    )
    storage_key = models.FileField(upload_to="library/%Y/%m/")
    original_name = models.CharField(max_length=255)
    detected_mime = models.CharField(max_length=100, default="application/octet-stream")
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    remark = models.CharField(max_length=500, blank=True, default="")
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="desktop")
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="ready")
    tags = models.ManyToManyField(Tag, related_name="materials", blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "deleted_at", "state"]),
            models.Index(fields=["owner", "folder"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.original_name


class TaskMaterial(VersionedModel):
    """Attachment between a task and a material of the same owner."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_materials")
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name="task_materials"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "material"],
                name="workspace_taskmaterial_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.task_id}:{self.material_id}"


class UploadSession(models.Model):
    """A short lived, delivery-only credential created by the desktop owner."""

    STATE_CHOICES = [
        ("active", "接收中"),
        ("revoked", "已撤销"),
        ("closed", "已结束"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="upload_sessions",
    )
    token_digest = models.CharField(max_length=64, unique=True)
    destination_folder = models.ForeignKey(
        Folder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="upload_sessions",
    )
    destination_task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="upload_sessions",
    )
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="active")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    max_files = models.PositiveIntegerField(default=20)
    max_bytes = models.BigIntegerField(default=1024 * 1024 * 1024)
    max_file_bytes = models.BigIntegerField(default=1024 * 1024 * 1024)
    reserved_files = models.PositiveIntegerField(default=0)
    reserved_bytes = models.BigIntegerField(default=0)
    committed_files = models.PositiveIntegerField(default=0)
    committed_bytes = models.BigIntegerField(default=0)
    used_bytes = models.BigIntegerField(default=0)
    auth_version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "state", "expires_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return f"upload-session:{self.id}"


class UploadReceipt(models.Model):
    """One file transfer inside an upload session."""

    STATE_CHOICES = [
        ("reserved", "已预占"),
        ("receiving", "接收中"),
        ("committed", "已完成"),
        ("failed", "失败"),
        ("expired", "已过期"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        UploadSession, on_delete=models.CASCADE, related_name="receipts"
    )
    client_upload_id = models.CharField(max_length=64)
    original_name = models.CharField(max_length=255)
    declared_size = models.BigIntegerField(default=0)
    actual_size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="reserved")
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    failure_code = models.CharField(max_length=64, blank=True, default="")
    material = models.OneToOneField(
        Material, null=True, blank=True, on_delete=models.SET_NULL, related_name="receipt"
    )
    attempt_id = models.UUIDField(default=uuid.uuid4)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "client_upload_id"],
                name="workspace_uploadreceipt_session_client_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"receipt:{self.id}:{self.state}"


class DailyEntry(VersionedModel):
    """One free form note per owner per calendar day."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_entries",
    )
    date = models.DateField()
    content = models.TextField(max_length=50000, blank=True, default="")

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "date"],
                name="workspace_dailyentry_owner_date_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.owner_id}:{self.date}"
