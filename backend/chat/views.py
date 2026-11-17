from __future__ import annotations

import mimetypes
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.db.models import Max, Q
from django.utils import timezone
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from config.streaming import stream_chunks

from .models import BBSPost, BBSReply, ChatMessage, ChatReadState
from accounts.permissions import is_super_admin
from accounts.models import AccountProfile
from .permissions import IsChatUser, can_chat_with, CanUseForum
from .serializers import (
    BBSPostSerializer,
    BBSPostListSerializer,
    BBSPostWriteSerializer,
    BBSReplySerializer,
    BBSReplyWriteSerializer,
    ChatMessageSerializer,
)

ALLOWED_CHAT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".zip",
    ".rar",
    ".7z",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_CHAT_FILE_BYTES = 1024 * 1024 * 1024


def partner_for(user: User, username: str | None = None) -> User | None:
    if is_super_admin(user):
        queryset = User.objects.filter(is_active=True).exclude(pk=user.pk)
        if username:
            return next((item for item in queryset if item.username == username and can_chat_with(user, item)), None)
        return None
    super_user = User.objects.filter(username="qzx", is_active=True).first()
    if super_user and can_chat_with(user, super_user) and (not username or username == super_user.username):
        return super_user
    return None


def messages_for(user: User):
    return ChatMessage.objects.filter(
        Q(sender=user, deleted_for_sender=False)
        | Q(recipient=user, deleted_for_recipient=False)
    )


def conversation_messages(user: User, partner: User):
    return all_conversation_messages(user, partner).filter(
        Q(sender=user, deleted_for_sender=False)
        | Q(recipient=user, deleted_for_recipient=False)
    )


def all_conversation_messages(user: User, partner: User):
    return ChatMessage.objects.filter(
        (Q(sender=user, recipient=partner) | Q(sender=partner, recipient=user))
    )


def unread_count_for(user: User) -> int:
    state = ChatReadState.objects.filter(user=user).first()
    queryset = ChatMessage.objects.filter(recipient=user, deleted_for_recipient=False)
    if state and state.last_read_at:
        queryset = queryset.filter(created_at__gt=state.last_read_at)
    return queryset.count()


def mark_read_for(user: User) -> None:
    latest = ChatMessage.objects.filter(recipient=user, deleted_for_recipient=False).aggregate(
        latest=Max("created_at")
    )["latest"]
    acknowledged_at = latest or timezone.now()
    state, _ = ChatReadState.objects.get_or_create(user=user)
    if state.last_read_at is None or acknowledged_at > state.last_read_at:
        state.last_read_at = acknowledged_at
        state.save(update_fields=["last_read_at", "updated_at"])


@api_view(["GET"])
@permission_classes([IsChatUser])
def contacts(request):
    if is_super_admin(request.user):
        users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by("username")
        users = [user for user in users if can_chat_with(request.user, user)]
    else:
        user = User.objects.filter(username="qzx", is_active=True).first()
        users = [user] if user and can_chat_with(request.user, user) else []
    return Response({"contacts": [{"username": user.username, "name": user.get_full_name() or user.username} for user in users]})


def broadcast_message(message: ChatMessage) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = {"type": "chat.message", "message": ChatMessageSerializer(message).data}
    async_to_sync(channel_layer.group_send)(f"chat_user_{message.sender_id}", payload)
    if message.recipient_id:
        async_to_sync(channel_layer.group_send)(f"chat_user_{message.recipient_id}", payload)


def broadcast_deleted(message: ChatMessage, viewer: User | None = None) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    event = {"type": "chat.deleted", "message_id": str(message.id)}
    if viewer is None or viewer.pk == message.sender_id:
        async_to_sync(channel_layer.group_send)(f"chat_user_{message.sender_id}", event)
    if message.recipient_id and (viewer is None or viewer.pk == message.recipient_id):
        async_to_sync(channel_layer.group_send)(f"chat_user_{message.recipient_id}", event)


def broadcast_cleared(user: User, partner: User, everyone: bool) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"chat_user_{user.pk}", {"type": "chat.cleared", "partner": partner.username}
    )
    if everyone:
        async_to_sync(channel_layer.group_send)(
            f"chat_user_{partner.pk}", {"type": "chat.cleared", "partner": user.username}
        )


@api_view(["GET", "POST"])
@permission_classes([IsChatUser])
def messages(request):
    partner = partner_for(request.user, request.query_params.get("with"))
    if partner is None:
        return Response({"detail": "请选择一个可聊天的账号。"}, status=400)
    if request.method == "GET":
        base = conversation_messages(request.user, partner)
        queryset = list(base.select_related("sender").order_by("-created_at")[:200])
        queryset.reverse()
        mark_read_for(request.user)
        return Response(
            ChatMessageSerializer(queryset, many=True).data,
            headers={"Cache-Control": "private, no-store"},
        )

    content = str(request.data.get("content") or "").strip()
    if not content:
        return Response({"detail": "留言不能为空。"}, status=400)
    if len(content) > 5000:
        return Response({"detail": "留言不能超过 5000 个字符。"}, status=400)
    message = ChatMessage.objects.create(
        sender=request.user,
        recipient=partner,
        message_type="text",
        content=content,
    )
    payload = ChatMessageSerializer(message).data
    broadcast_message(message)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsChatUser])
def message_detail(request, message_id):
    message = get_object_or_404(messages_for(request.user), pk=message_id)
    scope = request.query_params.get("scope", "self")
    if scope != "self":
        return Response(
            {"detail": "聊天记录需保留在服务器，只能从自己的列表中隐藏。"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    field = (
        "deleted_for_sender"
        if message.sender_id == request.user.pk
        else "deleted_for_recipient"
    )
    if not getattr(message, field):
        setattr(message, field, True)
        message.save(update_fields=[field])
    broadcast_deleted(message, viewer=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["DELETE"])
@permission_classes([IsChatUser])
def clear_messages(request):
    partner = partner_for(request.user, request.query_params.get("with"))
    if partner is None:
        return Response({"detail": "请选择一个可聊天的账号。"}, status=400)
    scope = request.query_params.get("scope", "self")
    if scope != "self":
        return Response(
            {"detail": "聊天记录需保留在服务器，只能清空自己的列表。"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    conversation = all_conversation_messages(request.user, partner)
    sent = conversation.filter(sender=request.user, deleted_for_sender=False).update(
        deleted_for_sender=True
    )
    received = conversation.filter(
        recipient=request.user, deleted_for_recipient=False
    ).update(deleted_for_recipient=True)
    broadcast_cleared(request.user, partner, False)
    return Response({"deleted": sent + received})


@api_view(["GET"])
@permission_classes([IsChatUser])
def unread(request):
    return Response(
        {"count": unread_count_for(request.user)},
        headers={"Cache-Control": "private, no-store"},
    )


@api_view(["POST"])
@permission_classes([IsChatUser])
def mark_read(request):
    mark_read_for(request.user)
    return Response({"count": 0})


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsChatUser])
def upload_file(request):
    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "请选择要发送的文件。"}, status=400)
    if upload.size <= 0:
        return Response({"detail": "不能发送空文件。"}, status=400)
    if upload.size > MAX_CHAT_FILE_BYTES:
        return Response({"detail": "文件超过 1 GB。"}, status=400)
    suffix = Path(upload.name or "").suffix.lower()
    if suffix not in ALLOWED_CHAT_EXTENSIONS:
        return Response(
            {"detail": "暂不支持该文件类型。"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    partner = partner_for(request.user, request.query_params.get("with") or request.data.get("with"))
    if partner is None:
        return Response({"detail": "对方账号尚未初始化。"}, status=503)

    caption = str(request.data.get("content") or "").strip()[:5000]
    content_type = mimetypes.guess_type(upload.name or "")[0] or "application/octet-stream"
    message = ChatMessage(
        sender=request.user,
        recipient=partner,
        message_type="file",
        content=caption,
        file_name=Path(upload.name or "文件").name[:255],
        file_size=upload.size,
        file_type=content_type[:100],
    )
    message.file.save(message.file_name, upload, save=False)
    message.save()
    payload = ChatMessageSerializer(message).data
    broadcast_message(message)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsChatUser])
def download_file(request, message_id):
    message = get_object_or_404(messages_for(request.user), pk=message_id, message_type="file")
    if not message.file:
        return Response({"detail": "文件不存在。"}, status=404)
    try:
        handle = message.file.open("rb")
    except (FileNotFoundError, OSError):
        return Response({"detail": "文件已从磁盘移除。"}, status=404)

    suffix = Path(message.file_name or message.file.name).suffix.lower()
    is_safe_image = suffix in IMAGE_EXTENSIONS
    inline = is_safe_image and request.query_params.get("inline") in {"1", "true"}
    content_type = (
        mimetypes.guess_type(f"image{suffix}")[0] if inline else "application/octet-stream"
    )

    response = FileResponse(
        handle,
        as_attachment=not inline,
        filename=message.file_name or Path(message.file.name).name,
        content_type=content_type,
    )
    response.block_size = 64 * 1024
    response.streaming_content = stream_chunks(request, response.streaming_content)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response


# ---------------------------------------------------------------------------
# 留言板（贴吧式）—— BBSPost / BBSReply
# ---------------------------------------------------------------------------

ALLOWED_BBS_EXTENSIONS = ALLOWED_CHAT_EXTENSIONS.copy()


def _bbs_visible_queryset(user: User):
    """返回当前用户可见的帖子集合：公开 + 指定自己的 + 自己创建的。"""
    qs = BBSPost.objects.filter(visibility="public") | BBSPost.objects.filter(
        author=user
    ) | BBSPost.objects.filter(visible_to=user)
    return qs.distinct()


@api_view(["GET", "POST"])
@permission_classes([CanUseForum])
def bbs_posts(request):
    """帖子列表（GET）或发帖（POST）。"""
    if request.method == "GET":
        queryset = _bbs_visible_queryset(request.user).select_related("author").order_by("-created_at")[:100]
        data = BBSPostListSerializer(queryset, many=True).data
        return Response(data, headers={"Cache-Control": "private, no-store"})

    # POST — 发帖
    serializer = BBSPostWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    title = serializer.validated_data["title"]
    content = serializer.validated_data["content"]
    visibility = serializer.validated_data["visibility"]
    visible_to_names = serializer.validated_data.get("visible_to", [])

    post = BBSPost.objects.create(
        author=request.user,
        title=title,
        content=content,
        visibility=visibility,
    )
    if visible_to_names:
        visible_users = list(
            User.objects.filter(username__in=visible_to_names, is_active=True)
        )
        post.visible_to.set(visible_users)

    upload = request.FILES.get("file")
    if upload and upload.size > 0:
        if upload.size > MAX_CHAT_FILE_BYTES:
            post.delete()
            return Response({"detail": "文件超过 1 GB。"}, status=400)
        suffix = Path(upload.name or "").suffix.lower()
        if suffix not in ALLOWED_BBS_EXTENSIONS:
            post.delete()
            return Response(
                {"detail": "暂不支持该文件类型。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content_type = mimetypes.guess_type(upload.name or "")[0] or "application/octet-stream"
        post.file.save(Path(upload.name or "文件").name[:255], upload, save=False)
        post.file_name = Path(upload.name or "文件").name[:255]
        post.file_size = upload.size
        post.file_type = content_type[:100]
        post.save(update_fields=["file", "file_name", "file_size", "file_type"])

    payload = BBSPostSerializer(post).data
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
@permission_classes([CanUseForum])
def bbs_post_detail(request, post_id):
    """帖子详情（含回复列表）或删除帖子。"""
    post = get_object_or_404(_bbs_visible_queryset(request.user), pk=post_id)

    if request.method == "GET":
        # 刷新 reply_count
        post.reply_count = post.replies.count()
        post.last_reply_at = (
            post.replies.order_by("-created_at").values_list("created_at", flat=True).first()
        )
        if post.last_reply_at:
            post.save(update_fields=["reply_count", "last_reply_at"])
        data = BBSPostSerializer(post).data
        return Response(data, headers={"Cache-Control": "private, no-store"})

    # DELETE — 作者或最高管理员可删除自己的帖子（物理删除）
    if request.user.pk != post.author_id and not is_super_admin(request.user):
        return Response(
            {"detail": "只有帖子作者可以删除。"},
            status=status.HTTP_403_FORBIDDEN,
        )
    deleted_title = post.title
    try:
        if post.file:
            post.file.delete(save=False)
    except OSError:
        pass
    post.delete()
    audit_log(
        request,
        "bbs_post_deleted",
        user=request.user,
        detail=f"title={deleted_title}",
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([CanUseForum])
def bbs_post_replies(request, post_id):
    """给帖子添加回复（可带附件）。"""
    post = get_object_or_404(_bbs_visible_queryset(request.user), pk=post_id)
    serializer = BBSReplyWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    content = serializer.validated_data["content"]

    reply = BBSReply.objects.create(
        post=post,
        author=request.user,
        content=content,
    )

    upload = request.FILES.get("file")
    if upload and upload.size > 0:
        if upload.size > MAX_CHAT_FILE_BYTES:
            reply.delete()
            return Response({"detail": "文件超过 1 GB。"}, status=400)
        suffix = Path(upload.name or "").suffix.lower()
        if suffix not in ALLOWED_BBS_EXTENSIONS:
            reply.delete()
            return Response(
                {"detail": "暂不支持该文件类型。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content_type = mimetypes.guess_type(upload.name or "")[0] or "application/octet-stream"
        reply.file.save(Path(upload.name or "文件").name[:255], upload, save=False)
        reply.file_name = Path(upload.name or "文件").name[:255]
        reply.file_size = upload.size
        reply.file_type = content_type[:100]
        reply.save(update_fields=["file", "file_name", "file_size", "file_type"])

    # 更新帖子的回复计数
    post.reply_count = post.replies.count()
    post.last_reply_at = reply.created_at
    post.save(update_fields=["reply_count", "last_reply_at"])

    data = BBSReplySerializer(reply).data
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([CanUseForum])
def bbs_reply_detail(request, post_id, reply_id):
    """删除自己的回复（物理删除）。"""
    reply = get_object_or_404(BBSReply.objects.select_related("post"), pk=reply_id)
    if request.user.pk != reply.author_id and not is_super_admin(request.user):
        return Response(
            {"detail": "只有回复作者可以删除。"},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        if reply.file:
            reply.file.delete(save=False)
    except OSError:
        pass
    reply.delete()
    # 更新帖子计数
    post = reply.post
    post.reply_count = max(0, post.replies.count())
    post.last_reply_at = (
        post.replies.order_by("-created_at").values_list("created_at", flat=True).first()
    )
    if post.last_reply_at:
        post.save(update_fields=["reply_count", "last_reply_at"])
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([CanUseForum])
def bbs_post_download_file(request, post_id):
    """下载帖子附件。"""
    post = get_object_or_404(_bbs_visible_queryset(request.user), pk=post_id)
    if not post.file:
        return Response({"detail": "文件不存在。"}, status=404)
    try:
        handle = post.file.open("rb")
    except (FileNotFoundError, OSError):
        return Response({"detail": "文件已从磁盘移除。"}, status=404)

    suffix = Path(post.file_name or post.file.name).suffix.lower()
    is_safe_image = suffix in IMAGE_EXTENSIONS
    inline = is_safe_image and request.query_params.get("inline") in {"1", "true"}
    content_type = (
        mimetypes.guess_type(f"image{suffix}")[0] if inline else "application/octet-stream"
    )

    response = FileResponse(
        handle,
        as_attachment=not inline,
        filename=post.file_name or Path(post.file.name).name,
        content_type=content_type,
    )
    response.block_size = 64 * 1024
    response.streaming_content = stream_chunks(request, response.streaming_content)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response


@api_view(["GET"])
@permission_classes([CanUseForum])
def bbs_reply_download_file(request, reply_id):
    """下载回复附件。"""
    reply = get_object_or_404(BBSReply.objects.select_related("post"), pk=reply_id)
    if not reply.file:
        return Response({"detail": "文件不存在。"}, status=404)
    try:
        handle = reply.file.open("rb")
    except (FileNotFoundError, OSError):
        return Response({"detail": "文件已从磁盘移除。"}, status=404)

    suffix = Path(reply.file_name or reply.file.name).suffix.lower()
    is_safe_image = suffix in IMAGE_EXTENSIONS
    inline = is_safe_image and request.query_params.get("inline") in {"1", "true"}
    content_type = (
        mimetypes.guess_type(f"image{suffix}")[0] if inline else "application/octet-stream"
    )

    response = FileResponse(
        handle,
        as_attachment=not inline,
        filename=reply.file_name or Path(reply.file.name).name,
        content_type=content_type,
    )
    response.block_size = 64 * 1024
    response.streaming_content = stream_chunks(request, response.streaming_content)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response


def audit_log(request, action, user=None, detail=""):
    """轻量审计记录写入 ActivityLog。"""
    from accounts.models import ActivityLog
    ActivityLog.objects.create(
        user=user,
        actor=request.user,
        action=action,
        detail=detail,
        ip=_client_ip(request),
    )


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
