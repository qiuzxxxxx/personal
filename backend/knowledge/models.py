"""Personal knowledge base and personal memory models.

Every record is owner scoped. The owner always comes from the request token;
clients can never write it. Sources keep an explicit link to the original
object (material / daily entry / assistant message) so that withdrawing a
source can stop the derived knowledge from being used.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from config.models import VersionedModel

SOURCE_TYPE_CHOICES = [
    ("manual", "手写笔记"),
    ("material", "私人资料"),
    ("journal_entry", "每日记录"),
    ("ai_message", "AI 消息"),
]

CONTENT_ORIGIN_CHOICES = [
    ("user_authored", "用户撰写"),
    ("source_snapshot", "来源快照"),
    ("ai_generated", "模型生成"),
]

INDEX_STATUS_CHOICES = [
    ("pending", "排队中"),
    ("processing", "解析中"),
    ("ready", "可检索"),
    ("failed", "失败"),
    ("needs_ocr", "需要 OCR"),
    ("stale", "来源已更新"),
]

MEMORY_KIND_CHOICES = [
    ("fact", "事实"),
    ("preference", "偏好"),
    ("goal", "目标"),
]

MEMORY_SCOPE_CHOICES = [
    ("global", "全局"),
    ("project", "项目"),
]

MEMORY_STATUS_CHOICES = [
    ("suggested", "候选"),
    ("active", "已启用"),
    ("disabled", "已停用"),
    ("superseded", "已被替代"),
    ("forgotten", "已忘记"),
]

EVIDENCE_TYPE_CHOICES = [
    ("user_explicit", "用户明确表示"),
    ("inferred", "自动提炼"),
]

JOB_STATUS_CHOICES = [
    ("pending", "待处理"),
    ("processing", "处理中"),
    ("done", "已完成"),
    ("failed", "失败"),
]


class KnowledgeCollection(VersionedModel):
    """A named group of knowledge documents."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_collections",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=2000, blank=True, default="")
    project = models.ForeignKey(
        "workspace.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="knowledge_collections",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["owner", "deleted_at"])]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class KnowledgeRevision(models.Model):
    """One extracted body of a knowledge document."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        "KnowledgeDocument",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_no = models.PositiveIntegerField(default=1)
    source_version = models.PositiveIntegerField(default=1)
    source_hash = models.CharField(max_length=64, blank=True, default="")
    parser_version = models.CharField(max_length=32, default="v1")
    body = models.TextField(blank=True, default="")
    index_status = models.CharField(
        max_length=16, choices=INDEX_STATUS_CHOICES, default="pending"
    )
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_detail = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    indexed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-revision_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "revision_no"],
                name="knowledge_revision_document_no_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.document_id}:{self.revision_no}"


class KnowledgeDocument(VersionedModel):
    """A knowledge entry: a manual note or a snapshot of another object."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_documents",
    )
    collection = models.ForeignKey(
        KnowledgeCollection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )
    title = models.CharField(max_length=200)
    source_type = models.CharField(
        max_length=20, choices=SOURCE_TYPE_CHOICES, default="manual"
    )
    source_material = models.ForeignKey(
        "workspace.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="knowledge_documents",
    )
    source_entry = models.ForeignKey(
        "workspace.DailyEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="knowledge_documents",
    )
    source_message = models.ForeignKey(
        "agent.Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="knowledge_documents",
    )
    manual_body = models.TextField(blank=True, default="")
    content_origin = models.CharField(
        max_length=20, choices=CONTENT_ORIGIN_CHOICES, default="user_authored"
    )
    ai_enabled = models.BooleanField(default=False)
    source_version = models.PositiveIntegerField(default=1)
    current_revision = models.ForeignKey(
        KnowledgeRevision,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_for",
    )
    source_title = models.CharField(max_length=300, blank=True, default="")
    source_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "deleted_at"]),
            models.Index(fields=["owner", "collection"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "source_material"],
                condition=Q(source_material__isnull=False, deleted_at__isnull=True),
                name="knowledge_document_owner_material_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return self.title

    @property
    def index_status(self) -> str:
        if self.current_revision_id is None:
            return "pending"
        return self.current_revision.index_status


class KnowledgeChunk(models.Model):
    """A retrievable slice of one revision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_chunks",
    )
    document = models.ForeignKey(
        KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks"
    )
    revision = models.ForeignKey(
        KnowledgeRevision, on_delete=models.CASCADE, related_name="chunks"
    )
    ordinal = models.PositiveIntegerField(default=0)
    text = models.TextField(blank=True, default="")
    content_hash = models.CharField(max_length=64, blank=True, default="")
    heading_path = models.CharField(max_length=300, blank=True, default="")
    page_start = models.PositiveIntegerField(null=True, blank=True)
    page_end = models.PositiveIntegerField(null=True, blank=True)
    char_start = models.PositiveIntegerField(null=True, blank=True)
    char_end = models.PositiveIntegerField(null=True, blank=True)
    token_estimate = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordinal"]
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "ordinal"],
                name="knowledge_chunk_revision_ordinal_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.document_id}:{self.ordinal}"


class KnowledgeIndexJob(models.Model):
    """A persistent parse/index job with a lease and a claim token."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_jobs",
    )
    document = models.ForeignKey(
        KnowledgeDocument, on_delete=models.CASCADE, related_name="jobs"
    )
    revision = models.ForeignKey(
        KnowledgeRevision, on_delete=models.CASCADE, related_name="jobs"
    )
    pipeline_version = models.CharField(max_length=32, default="v1")
    status = models.CharField(
        max_length=16, choices=JOB_STATUS_CHOICES, default="pending"
    )
    attempts = models.PositiveIntegerField(default=0)
    lease_until = models.DateTimeField(null=True, blank=True)
    claim_token = models.CharField(max_length=64, blank=True, default="")
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "revision", "pipeline_version"],
                name="knowledge_job_document_revision_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"job:{self.id}"


class PersonalMemory(VersionedModel):
    """A confirmed preference, fact or goal of the account owner."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_memories",
    )
    key = models.CharField(max_length=128)
    content = models.TextField(blank=True, default="")
    kind = models.CharField(
        max_length=16, choices=MEMORY_KIND_CHOICES, default="preference"
    )
    scope_type = models.CharField(
        max_length=16, choices=MEMORY_SCOPE_CHOICES, default="global"
    )
    project = models.ForeignKey(
        "workspace.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="personal_memories",
    )
    status = models.CharField(
        max_length=16, choices=MEMORY_STATUS_CHOICES, default="suggested"
    )
    evidence_type = models.CharField(
        max_length=20, choices=EVIDENCE_TYPE_CHOICES, default="user_explicit"
    )
    source_ref = models.CharField(max_length=255, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by"
    )
    seed_key = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["owner", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "key", "scope_type"],
                condition=Q(status="active"),
                name="knowledge_memory_active_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.key}:{self.status}"


class MemoryRevision(models.Model):
    """Change history of a personal memory (no owner content after forget)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memory = models.ForeignKey(
        PersonalMemory, on_delete=models.CASCADE, related_name="revisions"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memory_revisions",
    )
    action = models.CharField(max_length=32)
    version = models.PositiveIntegerField(default=1)
    body_snapshot = models.TextField(blank=True, default="")
    actor = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.memory_id}:{self.action}"


class KnowledgeWriteIntent(models.Model):
    """A user-triggered, schema-checked write permission for one turn."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_write_intents",
    )
    conversation = models.ForeignKey(
        "agent.Conversation",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="knowledge_write_intents",
    )
    target = models.CharField(max_length=32)
    payload = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "idempotency_key"],
                name="knowledge_write_intent_idempotent_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"intent:{self.id}"


class MessageCitation(models.Model):
    """A citation bound to one assistant message of the owner."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_citations",
    )
    message = models.ForeignKey(
        "agent.Message", on_delete=models.CASCADE, related_name="citations"
    )
    source_id = models.CharField(max_length=16)
    source_type = models.CharField(max_length=20)
    document = models.ForeignKey(
        KnowledgeDocument,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="citations",
    )
    revision = models.ForeignKey(
        KnowledgeRevision,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="citations",
    )
    chunk = models.ForeignKey(
        KnowledgeChunk,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="citations",
    )
    locator = models.JSONField(default=dict, blank=True)
    snapshot_text = models.CharField(max_length=1000, blank=True, default="")
    retrieved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["retrieved_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["message", "source_id"],
                name="knowledge_citation_message_source_unique",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.message_id}:{self.source_id}"


class OwnerContextState(models.Model):
    """Per owner context epoch used to invalidate injected history."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_context_state",
    )
    epoch = models.PositiveIntegerField(default=1)
    floor_epoch = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"context:{self.owner_id}@{self.epoch}"


class ReviewCard(VersionedModel):
    """SM-2 spaced-repetition card owned by one account."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_cards",
    )
    document = models.ForeignKey(
        KnowledgeDocument,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_cards",
    )
    front = models.CharField(max_length=300)
    back = models.TextField(max_length=10000)
    tag = models.CharField(max_length=64, blank=True, default="408复习")
    interval_days = models.PositiveIntegerField(default=1)
    ease_factor = models.FloatField(default=2.5)
    repetitions = models.PositiveIntegerField(default=0)
    next_review_at = models.DateTimeField(db_index=True, default=timezone.now)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["next_review_at", "created_at"]
        indexes = [
            models.Index(fields=["owner", "deleted_at", "next_review_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"review:{self.front[:24]}"
