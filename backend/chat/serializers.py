from rest_framework import serializers

from .models import BBSReply, BBSPost, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    sender_name = serializers.SerializerMethodField()
    recipient_username = serializers.CharField(
        source="recipient.username", read_only=True, allow_null=True
    )
    is_image = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender_username",
            "sender_name",
            "recipient_username",
            "message_type",
            "content",
            "file_name",
            "file_size",
            "file_type",
            "is_image",
            "file_url",
            "created_at",
        ]

    def get_sender_name(self, obj: ChatMessage) -> str:
        return obj.sender.get_full_name() or obj.sender.username

    def get_file_url(self, obj: ChatMessage) -> str:
        if obj.message_type != "file" or not obj.file:
            return ""
        return f"/api/chat/files/{obj.id}/download/"


class BBSReplySerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)
    author_name = serializers.SerializerMethodField()
    is_image = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = BBSReply
        fields = [
            "id",
            "author_username",
            "author_name",
            "content",
            "file_name",
            "file_size",
            "file_type",
            "is_image",
            "file_url",
            "created_at",
        ]

    def get_author_name(self, obj: BBSReply) -> str:
        return obj.author.get_full_name() or obj.author.username

    def get_file_url(self, obj: BBSReply) -> str:
        if not obj.file:
            return ""
        return f"/api/chat/bbs/replies/{obj.id}/file/"


class BBSPostSerializer(serializers.ModelSerializer):
    """留言板主题详情（含回复）。"""

    author_username = serializers.CharField(source="author.username", read_only=True)
    author_name = serializers.SerializerMethodField()
    is_image = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()
    replies = BBSReplySerializer(many=True, read_only=True)

    class Meta:
        model = BBSPost
        fields = [
            "id",
            "author_username",
            "author_name",
            "title",
            "content",
            "visibility",
            "visible_to",
            "file_name",
            "file_size",
            "file_type",
            "is_image",
            "file_url",
            "reply_count",
            "last_reply_at",
            "replies",
            "created_at",
            "updated_at",
        ]

    def get_author_name(self, obj: BBSPost) -> str:
        return obj.author.get_full_name() or obj.author.username

    def get_file_url(self, obj: BBSPost) -> str:
        if not obj.file:
            return ""
        return f"/api/chat/bbs/posts/{obj.id}/file/"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["visible_to"] = list(
            instance.visible_to.values_list("username", flat=True)
        )
        return data


class BBSPostListSerializer(BBSPostSerializer):
    """消息板列表：不加载回复，仅摘要字段。"""

    class Meta:
        model = BBSPost
        fields = [
            "id",
            "author_username",
            "author_name",
            "title",
            "content",
            "visibility",
            "visible_to",
            "file_name",
            "file_size",
            "file_type",
            "is_image",
            "file_url",
            "reply_count",
            "last_reply_at",
            "created_at",
            "updated_at",
        ]

    def get_replies(self, obj):  # pragma: no cover - not used in the list view
        return []


class BBSPostWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120, allow_blank=True)
    content = serializers.CharField(max_length=5000, allow_blank=True)
    visibility = serializers.ChoiceField(choices=["public", "private"], default="public")
    visible_to = serializers.ListField(
        child=serializers.CharField(max_length=150), required=False, default=list
    )

    def validate(self, attrs):
        title = attrs.get("title", "").strip()
        content = attrs.get("content", "").strip()
        if not title and not content:
            raise serializers.ValidationError("标题和正文不能同时为空。")
        attrs["title"] = title[:120]
        attrs["content"] = content[:5000]
        return attrs


class BBSReplyWriteSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=5000, allow_blank=True)

    def validate(self, attrs):
        content = attrs.get("content", "").strip()
        if not content:
            raise serializers.ValidationError("回复内容不能为空。")
        attrs["content"] = content
        return attrs
