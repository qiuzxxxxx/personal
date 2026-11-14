from pathlib import Path

from rest_framework import serializers

from .crypto import decrypt_secret, mask_secret
from .models import AgentAttachment, Conversation, Message, UserApiConfig


class UserApiConfigSerializer(serializers.ModelSerializer):
    """Never exposes the plaintext key: only a presence flag and a hint."""

    has_key = serializers.BooleanField(read_only=True)
    key_hint = serializers.SerializerMethodField()

    class Meta:
        model = UserApiConfig
        fields = [
            "provider",
            "base_url",
            "model",
            "system_prompt",
            "has_key",
            "key_hint",
            "updated_at",
        ]

    def get_key_hint(self, obj: UserApiConfig) -> str:
        if not obj.api_key_cipher:
            return ""
        return mask_secret(decrypt_secret(obj.api_key_cipher))


class AgentAttachmentSerializer(serializers.ModelSerializer):
    extension = serializers.CharField(read_only=True)

    class Meta:
        model = AgentAttachment
        fields = [
            "id",
            "original_name",
            "mime_type",
            "file_size",
            "is_image",
            "extension",
        ]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "role",
            "content",
            "attachments",
            "knowledge_sources",
            "created_at",
        ]


class ConversationSummarySerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "message_count",
            "last_message",
            "knowledge_enabled",
            "knowledge_scope",
            "knowledge_collection_ids",
            "use_personal_memory",
            "use_workspace",
            "strict_sources",
            "knowledge_project",
            "created_at",
            "updated_at",
        ]

    def get_message_count(self, obj: Conversation) -> int:
        return len(obj.messages.all())

    def get_last_message(self, obj: Conversation) -> str:
        messages = list(obj.messages.all())
        if not messages:
            return ""
        content = messages[-1].content.strip()
        return content[:80]


class ConversationDetailSerializer(ConversationSummarySerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSummarySerializer.Meta):
        fields = ConversationSummarySerializer.Meta.fields + ["messages"]


class AttachmentRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField(max_length=255)
    mime = serializers.CharField(allow_blank=True)
    size = serializers.IntegerField(min_value=0)
    is_image = serializers.BooleanField()


class KnowledgeScopeSerializer(serializers.Serializer):
    """Optional per-turn knowledge scope for the chat endpoint."""

    enabled = serializers.BooleanField(required=False, default=False)
    scope = serializers.ChoiceField(
        choices=["all", "collections"], required=False, default="all"
    )
    collection_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=50
    )
    use_personal_memory = serializers.BooleanField(required=False, default=False)
    project_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    use_workspace = serializers.BooleanField(required=False, default=False)
    strict_sources = serializers.BooleanField(required=False, default=False)


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True, max_length=50000)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=8
    )
    api_config = serializers.DictField()
    knowledge = serializers.JSONField(required=False, default=dict)

    def validate_api_config(self, value):
        base_url = str(value.get("base_url") or "").strip()
        if base_url and not base_url.lower().startswith(("http://", "https://")):
            raise serializers.ValidationError("Base URL 必须以 http:// 或 https:// 开头。")
        return value

    def validate_knowledge(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("knowledge 必须是对象。")
        allowed = {
            "enabled",
            "scope",
            "collection_ids",
            "use_personal_memory",
            "project_id",
            "use_workspace",
            "strict_sources",
        }
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(
                f"knowledge 含有未知字段：{', '.join(sorted(unknown))}"
            )
        scope = str(value.get("scope") or "all")
        if scope not in {"all", "collections"}:
            raise serializers.ValidationError("scope 只能是 all 或 collections。")
        collection_ids = value.get("collection_ids") or []
        if not isinstance(collection_ids, list):
            raise serializers.ValidationError("collection_ids 必须是数组。")
        cleaned = {}
        for key in (
            "enabled",
            "use_personal_memory",
            "use_workspace",
            "strict_sources",
        ):
            if key in value:
                cleaned[key] = bool(value[key])
        cleaned["scope"] = scope
        cleaned["collection_ids"] = [str(item) for item in collection_ids][:50]
        project_id = value.get("project_id")
        cleaned["project_id"] = str(project_id) if project_id else ""
        return cleaned


class ConnectionTestSerializer(serializers.Serializer):
    provider = serializers.CharField(max_length=32)
    base_url = serializers.CharField(max_length=500)
    model = serializers.CharField(max_length=200)
    api_key = serializers.CharField(required=False, allow_blank=True, max_length=4096)
    clear_key = serializers.BooleanField(required=False, default=False)


def attachment_ref(attachment: AgentAttachment) -> dict:
    return {
        "id": str(attachment.id),
        "name": attachment.original_name,
        "mime": attachment.mime_type,
        "size": attachment.file_size,
        "is_image": attachment.is_image,
    }


def attachment_name_from_path(path: str) -> str:
    return Path(path).name or "文件"
