import uuid
from datetime import datetime
from pathlib import Path

from django.contrib.auth.models import User
from django.db import models

def chat_file_path(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()[:16]
    now = datetime.now()
    return f"chat_files/{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"


def bbs_file_path(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()[:16]
    now = datetime.now()
    return f"bbs/{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"


class ChatMessage(models.Model):
    TYPE_CHOICES = [("text", "文字"), ("file", "文件")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_messages_sent"
    )
    recipient = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="chat_messages_received",
    )
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="text")
    content = models.TextField(blank=True, default="")
    file = models.FileField(upload_to=chat_file_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True, default="")
    deleted_for_sender = models.BooleanField(default=False)
    deleted_for_recipient = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["created_at"])]

    @property
    def is_image(self) -> bool:
        return bool(self.file_type.startswith("image/"))

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.sender.username}: {self.message_type}"


class ChatReadState(models.Model):
    """Latest incoming message acknowledged by one chat participant."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="chat_read_state"
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"read:{self.user.username}@{self.last_read_at or 'never'}"


class BBSPost(models.Model):
    """站内留言板主题（贴吧式）：所有非访客成员公开可见、可按可见范围定向分享。"""

    VISIBILITY_CHOICES = [("public", "公开"), ("private", "指定可见")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bbs_posts"
    )
    title = models.CharField(max_length=120)
    content = models.TextField(blank=True, default="")
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default="public", db_index=True
    )
    visible_to = models.ManyToManyField(
        User, related_name="bbs_posts_shared", blank=True
    )
    file = models.FileField(upload_to=bbs_file_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True, default="")
    reply_count = models.PositiveIntegerField(default=0)
    last_reply_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_image(self) -> bool:
        return bool(self.file_type.startswith("image/"))

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.author.username}: {self.title}"


class BBSReply(models.Model):
    """留言板回复：属于某个主题，作者可见性由主题决定。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        BBSPost, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bbs_replies"
    )
    content = models.TextField(blank=True, default="")
    file = models.FileField(upload_to=bbs_file_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    @property
    def is_image(self) -> bool:
        return bool(self.file_type.startswith("image/"))

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.author.username}: {self.content[:40]}"
