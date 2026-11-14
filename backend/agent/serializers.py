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
        fields = ["id", "role", "content", "attachments", "created_at"]


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


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True, max_length=50000)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=8
    )
    api_config = serializers.DictField()

    def validate_api_config(self, value):
        base_url = str(value.get("base_url") or "").strip()
        if base_url and not base_url.lower().startswith(("http://", "https://")):
            raise serializers.ValidationError("Base URL 必须以 http:// 或 https:// 开头。")
        return value


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
