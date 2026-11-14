from __future__ import annotations

import mimetypes
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from config.streaming import stream_chunks

from .models import ChatMessage
from .permissions import IsChatUser
from .serializers import ChatMessageSerializer

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
MAX_CHAT_FILE_BYTES = 80 * 1024 * 1024


def partner_for(user: User) -> User | None:
    other = "sqx" if user.username == "qzx" else "qzx"
    return User.objects.filter(username=other, is_active=True).first()


def messages_for(user: User):
    return ChatMessage.objects.filter(Q(sender=user) | Q(recipient=user))


def broadcast_message(message: ChatMessage) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        "chat_pair",
        {
            "type": "chat.message",
            "message": ChatMessageSerializer(message).data,
        },
    )


@api_view(["GET", "POST"])
@permission_classes([IsChatUser])
def messages(request):
    if request.method == "GET":
        queryset = list(
            messages_for(request.user).select_related("sender").order_by("-created_at")[:200]
        )
        queryset.reverse()
        return Response(
            ChatMessageSerializer(queryset, many=True).data,
            headers={"Cache-Control": "private, no-store"},
        )

    content = str(request.data.get("content") or "").strip()
    if not content:
        return Response({"detail": "消息不能为空。"}, status=400)
    if len(content) > 5000:
        return Response({"detail": "消息不能超过 5000 个字符。"}, status=400)
    partner = partner_for(request.user)
    if partner is None:
        return Response({"detail": "对方账号尚未初始化。"}, status=503)

    message = ChatMessage.objects.create(
        sender=request.user,
        recipient=partner,
        message_type="text",
        content=content,
    )
    payload = ChatMessageSerializer(message).data
    broadcast_message(message)
    return Response(payload, status=status.HTTP_201_CREATED)


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
        return Response({"detail": "文件超过 80 MB。"}, status=400)
    suffix = Path(upload.name or "").suffix.lower()
    if suffix not in ALLOWED_CHAT_EXTENSIONS:
        return Response(
            {"detail": "暂不支持该文件类型。"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    partner = partner_for(request.user)
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
