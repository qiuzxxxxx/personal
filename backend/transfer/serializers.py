from pathlib import Path

from rest_framework import serializers

from .models import TransferFile


class TransferFileSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()

    class Meta:
        model = TransferFile
        fields = [
            "id",
            "original_name",
            "file_size",
            "file_type",
            "remark",
            "is_public",
            "visible_until",
            "uploader_name",
            "is_image",
            "extension",
            "download_url",
            "preview_url",
            "created_at",
            "updated_at",
        ]

    def get_download_url(self, obj: TransferFile) -> str:
        return f"/api/transfer/files/{obj.id}/download/"

    def get_preview_url(self, obj: TransferFile) -> str:
        if not self.get_is_image(obj):
            return ""
        return f"/api/transfer/files/{obj.id}/download/?inline=1"

    def get_is_image(self, obj: TransferFile) -> bool:
        return Path(obj.original_name).suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
        }

    def get_extension(self, obj: TransferFile) -> str:
        return Path(obj.original_name).suffix.lower().lstrip(".")
