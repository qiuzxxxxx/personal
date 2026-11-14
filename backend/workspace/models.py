"""Personal workspace models: projects, tasks, tags and daily entries.

Every record is owner scoped. The owner is taken from the request token and is
never accepted from client payloads.
"""
from __future__ import annotations

from django.conf import settings
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
