"""Serializers for the knowledge base APIs."""
from __future__ import annotations

from rest_framework import serializers

from .models import (
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeRevision,
    PersonalMemory,
)


class KnowledgeCollectionSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeCollection
        fields = [
            "id",
            "name",
            "description",
            "project",
            "project_name",
            "document_count",
            "version",
            "created_at",
            "updated_at",
        ]

    def get_project_name(self, obj) -> str:
        return obj.project.name if obj.project_id else ""

    def get_document_count(self, obj) -> int:
        return getattr(obj, "document_count", 0)


class KnowledgeRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeRevision
        fields = [
            "id",
            "revision_no",
            "source_version",
            "parser_version",
            "index_status",
            "error_code",
            "error_detail",
            "indexed_at",
            "created_at",
        ]


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    index_status = serializers.CharField(read_only=True)
    collection_name = serializers.SerializerMethodField()
    source_label = serializers.SerializerMethodField()
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = [
            "id",
            "title",
            "collection",
            "collection_name",
            "source_type",
            "source_label",
            "content_origin",
            "ai_enabled",
            "manual_body",
            "source_title",
            "source_date",
            "index_status",
            "chunk_count",
            "current_revision",
            "version",
            "created_at",
            "updated_at",
        ]

    def get_collection_name(self, obj) -> str:
        return obj.collection.name if obj.collection_id else ""

    def get_source_label(self, obj) -> str:
        if obj.source_type == "manual":
            return "手写笔记"
        if obj.source_type == "material":
            return obj.source_title or "私人资料"
        if obj.source_type == "journal_entry":
            return f"每日记录 {obj.source_date or ''}".strip()
        if obj.source_type == "ai_message":
            return "AI 消息"
        return obj.source_type

    def get_chunk_count(self, obj) -> int:
        return getattr(obj, "chunk_count", 0)


class KnowledgeDocumentWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True)
    collection = serializers.UUIDField(required=False, allow_null=True, default=None)
    manual_body = serializers.CharField(
        max_length=500000, required=False, allow_blank=True, default=""
    )
    ai_enabled = serializers.BooleanField(required=False, default=False)


class KnowledgeDocumentPatchSerializer(serializers.Serializer):
    """Partial update payload.

    ``collection`` deliberately carries no default: with a default it would
    always be present in ``validated_data`` and every title-only PATCH would
    silently move the document out of its collection.
    """

    title = serializers.CharField(
        max_length=200, allow_blank=False, trim_whitespace=True, required=False
    )
    collection = serializers.UUIDField(required=False, allow_null=True)
    manual_body = serializers.CharField(
        max_length=500000, required=False, allow_blank=True, default=None
    )
    ai_enabled = serializers.BooleanField(required=False, default=None)
    version = serializers.IntegerField(required=False, min_value=1)


class KnowledgeImportSerializer(serializers.Serializer):
    collection = serializers.UUIDField(required=False, allow_null=True, default=None)
    material = serializers.UUIDField(required=False, allow_null=True, default=None)
    entry = serializers.UUIDField(required=False, allow_null=True, default=None)
    message = serializers.UUIDField(required=False, allow_null=True, default=None)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    ai_enabled = serializers.BooleanField(required=False, default=False)
    client_request_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )


class MemorySerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = PersonalMemory
        fields = [
            "id",
            "key",
            "content",
            "kind",
            "scope_type",
            "project",
            "project_name",
            "status",
            "evidence_type",
            "source_ref",
            "confirmed_at",
            "valid_from",
            "valid_until",
            "version",
            "created_at",
            "updated_at",
        ]

    def get_project_name(self, obj) -> str:
        return obj.project.name if obj.project_id else ""


class MemoryWriteSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=128, allow_blank=False, trim_whitespace=True)
    content = serializers.CharField(max_length=20000, allow_blank=False, trim_whitespace=True)
    kind = serializers.ChoiceField(
        choices=["fact", "preference", "goal"], required=False, default="preference"
    )
    scope_type = serializers.ChoiceField(
        choices=["global", "project"], required=False, default="global"
    )
    project = serializers.UUIDField(required=False, allow_null=True, default=None)
    evidence_type = serializers.ChoiceField(
        choices=["user_explicit", "inferred"], required=False, default="user_explicit"
    )
    source_ref = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class MemoryPatchSerializer(serializers.Serializer):
    """Partial update payload.

    No field carries a default, so ``validated_data`` only contains the keys
    the client actually sent.  A defaulted ``project`` would be rewritten to
    None on every edit and would bypass the scope/project consistency check.
    """

    content = serializers.CharField(
        max_length=20000, allow_blank=False, trim_whitespace=True, required=False
    )
    kind = serializers.ChoiceField(choices=["fact", "preference", "goal"], required=False)
    scope_type = serializers.ChoiceField(choices=["global", "project"], required=False)
    project = serializers.UUIDField(required=False, allow_null=True)
    version = serializers.IntegerField(min_value=1)
