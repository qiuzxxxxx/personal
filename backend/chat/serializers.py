from rest_framework import serializers

from .models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    sender_name = serializers.SerializerMethodField()
    is_image = serializers.BooleanField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender_username",
            "sender_name",
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