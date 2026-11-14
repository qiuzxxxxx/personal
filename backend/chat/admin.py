from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "message_type", "created_at")
    list_filter = ("message_type",)
    search_fields = ("sender__username", "content", "file_name")