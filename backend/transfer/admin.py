from django.contrib import admin

from .models import TransferFile


@admin.register(TransferFile)
class TransferFileAdmin(admin.ModelAdmin):
    list_display = (
        "original_name",
        "uploader_name",
        "is_public",
        "file_size",
        "created_at",
    )
    list_filter = ("is_public",)
    search_fields = ("original_name", "remark", "uploader_name")