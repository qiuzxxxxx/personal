import uuid
from datetime import datetime
from pathlib import Path

from django.contrib.auth.models import User
from django.db import models

CHAT_USERNAMES = ("qzx", "sqx")


def chat_file_path(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()[:16]
    now = datetime.now()
    return f"chat_files/{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"


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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["created_at"])]

    @property
    def is_image(self) -> bool:
        return bool(self.file_type.startswith("image/"))

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.sender.username}: {self.message_type}"