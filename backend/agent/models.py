import uuid
from datetime import datetime
from pathlib import Path

from django.contrib.auth.models import User
from django.db import models


def agent_attachment_path(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()[:12]
    now = datetime.now()
    return f"agent_uploads/{now:%Y/%m}/{uuid.uuid4().hex}{suffix}"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )
    session_key = models.CharField(max_length=80, blank=True, db_index=True)
    title = models.CharField(max_length=120, default="新对话")
    # Knowledge scope of this conversation. All switches default to off so old
    # conversations keep their previous behaviour.
    knowledge_enabled = models.BooleanField(default=False)
    knowledge_scope = models.CharField(max_length=20, default="all")
    knowledge_collection_ids = models.JSONField(default=list, blank=True)
    use_personal_memory = models.BooleanField(default=False)
    use_workspace = models.BooleanField(default=False)
    strict_sources = models.BooleanField(default=False)
    knowledge_project = models.ForeignKey(
        "workspace.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agent_conversations",
    )
    context_epoch = models.PositiveIntegerField(default=1)
    # Set once reference material or personal memories were injected into
    # this conversation. Only such conversations are affected when a memory
    # is withdrawn; conversations that never used the knowledge base keep
    # their full history.
    context_injected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "-updated_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.title


class AgentAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="agent_attachments",
    )
    session_key = models.CharField(max_length=80, blank=True, db_index=True)
    file = models.FileField(upload_to=agent_attachment_path)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True, default="")
    file_size = models.BigIntegerField(default=0)
    extracted_text = models.TextField(blank=True, default="")
    is_image = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def extension(self) -> str:
        return Path(self.original_name).suffix.lower()

    def __str__(self) -> str:  # pragma: no cover
        return self.original_name


class Message(models.Model):
    ROLE_CHOICES = [("user", "用户"), ("assistant", "助手")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    attachments = models.JSONField(default=list, blank=True)
    # Metadata about the knowledge / memory context used for this turn.
    knowledge_sources = models.JSONField(default=list, blank=True)
    context_epoch = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.role}: {self.content[:40]}"


class UserApiConfig(models.Model):
    """Per-user model endpoint settings.

    The API key is stored ONLY as a Fernet ciphertext (see agent/crypto.py);
    the plaintext never touches the database and is never sent back to the
    browser after being saved.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="agent_api_config"
    )
    provider = models.CharField(max_length=32, default="custom")
    base_url = models.CharField(max_length=500, blank=True, default="")
    model = models.CharField(max_length=200, blank=True, default="")
    system_prompt = models.TextField(blank=True, default="")
    api_key_cipher = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "模型接口配置"
        verbose_name_plural = "模型接口配置"

    @property
    def has_key(self) -> bool:
        return bool(self.api_key_cipher)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.username} -> {self.model or '(unset)'}"