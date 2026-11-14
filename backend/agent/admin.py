from django.contrib import admin

from .models import AgentAttachment, Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "session_key", "updated_at")
    search_fields = ("title", "user__username")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at")
    list_filter = ("role",)


@admin.register(AgentAttachment)
class AgentAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "is_image", "file_size", "created_at")