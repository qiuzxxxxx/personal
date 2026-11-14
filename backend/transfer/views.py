from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.logging import client_ip
from accounts.logging import record as audit_log
from config.streaming import stream_chunks
from .models import TransferFile
from .permissions import IsTransferAdmin, is_transfer_admin
from .serializers import TransferFileSerializer

MAX_TRANSFER_BYTES = 500 * 1024 * 1024
# Anonymous uploads may not impersonate preset accounts in the uploader label.
RESERVED_UPLOADER_NAMES = {"qzx", "sqx", "yk"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
BLOCKED_EXTENSIONS = {
    ".exe",
    ".msi",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".ps1",
    ".vbs",
    ".js",
    ".jar",
}


def anonymous_upload_budget() -> int:
    """Total number of bytes anonymous uploads may occupy."""
    return int(getattr(settings, "TRANSFER_ANONYMOUS_TOTAL_BYTES", 0))


def anonymous_upload_window() -> int:
    """Seconds in which the anonymous total budget is measured."""
    return int(getattr(settings, "TRANSFER_ANONYMOUS_WINDOW_SECONDS", 3600))


def anonymous_upload_rate_limit() -> int:
    """Maximum number of anonymous uploads per hour."""
    return int(getattr(settings, "TRANSFER_ANONYMOUS_MAX_FILES_PER_WINDOW", 0))


def _budget_key(request) -> str:
    """The cache key of an anonymous client.

    The client address is resolved exactly like the login rate limit does,
    so that behind the reverse proxy every visitor gets their own budget
    instead of sharing the proxy's address.
    """
    address = client_ip(request) or "unknown"
    return f"transfer:anon:{address}"


def check_anonymous_budget(request) -> Response | None:
    """Reject anonymous uploads that would exceed the public budget.

    The public transfer station accepts files without an account, so it
    needs a total budget and a request rate limit: otherwise anonymous
    uploads can fill the disk.
    """
    total_budget = anonymous_upload_budget()
    file_budget = anonymous_upload_rate_limit()
    if not total_budget and not file_budget:
        return None
    key = _budget_key(request)
    used_bytes = cache.get(f"{key}:bytes") or 0
    used_files = cache.get(f"{key}:files") or 0
    if total_budget and used_bytes >= total_budget:
        return Response(
            {"detail": "免密上传总量已达上限，请稍后再试。"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if file_budget and used_files >= file_budget:
        return Response(
            {"detail": "免密上传次数已达上限，请稍后再试。"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


def record_anonymous_upload(request, size: int) -> None:
    """Count an anonymous upload against the public budget.

    The two counters are incremented atomically so that concurrent uploads
    cannot both pass the check.
    """
    total_budget = anonymous_upload_budget()
    file_budget = anonymous_upload_rate_limit()
    if not total_budget and not file_budget:
        return
    window = anonymous_upload_window()
    key = _budget_key(request)
    if total_budget:
        cache.add(f"{key}:bytes", 0, timeout=window)
        cache.incr(f"{key}:bytes", size)
        # Keep the window rolling with the last upload.
        cache.set(f"{key}:bytes", cache.get(f"{key}:bytes", 0), timeout=window)
    if file_budget:
        cache.add(f"{key}:files", 0, timeout=window)
        cache.incr(f"{key}:files", 1)
        cache.set(f"{key}:files", cache.get(f"{key}:files", 0), timeout=window)


def parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "public", "公开"}


def safe_original_name(raw: str) -> str:
    name = Path(str(raw or "").replace("\\", "/")).name.strip()
    name = name.replace("\x00", "")
    return (name or "未命名文件")[:255]


def inferred_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def is_self_uploaded(request, record: TransferFile) -> bool:
    return bool(
        getattr(request.user, "is_authenticated", False)
        and record.uploader_id == request.user.pk
    )


@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([AllowAny])
def files(request):
    if request.method == "GET":
        queryset = TransferFile.objects.all()
        if is_transfer_admin(request.user):
            pass  # Admin sees everything, including private drops.
        elif getattr(request.user, "is_authenticated", False):
            # Logged-in non-admin (e.g. guest): public files plus own uploads.
            queryset = queryset.filter(
                Q(is_public=True) | Q(uploader=request.user)
            )
        else:
            queryset = queryset.filter(is_public=True)
        return Response(
            TransferFileSerializer(queryset, many=True).data,
            headers={"Cache-Control": "private, no-store"},
        )

    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "请选择要上传的文件。"}, status=400)
    if upload.size <= 0:
        return Response({"detail": "不能上传空文件。"}, status=400)
    if upload.size > MAX_TRANSFER_BYTES:
        return Response({"detail": "文件超过 500 MB 限制。"}, status=413)

    owner = request.user if request.user.is_authenticated else None
    if owner is None:
        # Anonymous uploads share a public budget so that they cannot fill
        # the disk of the server.
        budget_error = check_anonymous_budget(request)
        if budget_error is not None:
            return budget_error

    original_name = safe_original_name(upload.name or "未命名文件")
    suffix = Path(original_name).suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        return Response(
            {"detail": "出于安全考虑，暂不支持上传可执行文件或脚本。"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    remark = str(request.data.get("remark") or "").strip()[:255]
    is_public = parse_bool(request.data.get("is_public"), default=True)
    if owner is not None:
        # Logged-in uploads are always attributed to the real account.
        uploader = owner.username
    else:
        raw_name = str(request.data.get("uploader_name") or "").strip()[:64]
        uploader = (
            raw_name
            if raw_name and raw_name.lower() not in RESERVED_UPLOADER_NAMES
            else "免密访客"
        )

    record = TransferFile(
        original_name=original_name,
        file_size=upload.size,
        file_type=inferred_mime(original_name),
        remark=remark,
        is_public=is_public,
        uploader_name=uploader,
        uploader=owner,
    )
    record.file.save(original_name, upload, save=False)
    record.save()
    if owner is None:
        record_anonymous_upload(request, record.file_size)
    audit_log(
        request,
        "transfer_upload",
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        detail=f"{original_name} public={is_public} by={uploader}",
    )
    return Response(
        TransferFileSerializer(record).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsTransferAdmin])
def file_detail(request, file_id):
    record = get_object_or_404(TransferFile, pk=file_id)

    if request.method == "DELETE":
        deleted_name = record.original_name
        try:
            record.file.delete(save=False)
        except OSError:
            pass
        record.delete()
        audit_log(request, "transfer_delete", user=request.user, detail=deleted_name)
        return Response(status=status.HTTP_204_NO_CONTENT)

    if "original_name" in request.data:
        raw_name = str(request.data.get("original_name") or "").strip()
        if not raw_name:
            return Response({"detail": "文件名不能为空。"}, status=400)
        record.original_name = safe_original_name(raw_name)
        record.file_type = inferred_mime(record.original_name)
    if "remark" in request.data:
        record.remark = str(request.data.get("remark") or "").strip()[:255]
    if "is_public" in request.data:
        record.is_public = parse_bool(request.data.get("is_public"), default=True)
    record.save()
    audit_log(
        request,
        "transfer_update",
        user=request.user,
        detail=f"{record.original_name} public={record.is_public}",
    )
    return Response(TransferFileSerializer(record).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def download(request, file_id):
    record = get_object_or_404(TransferFile, pk=file_id)
    if not record.is_public and not is_transfer_admin(request.user) and not is_self_uploaded(request, record):
        return Response(
            {"detail": "该文件为私密投递，仅上传者本人与管理员 qzx 可下载。"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not record.file:
        return Response({"detail": "文件不存在。"}, status=404)

    suffix = Path(record.original_name).suffix.lower()
    is_image = suffix in IMAGE_EXTENSIONS
    inline = is_image and request.query_params.get("inline") in {"1", "true"}
    content_type = inferred_mime(record.original_name) if inline else "application/octet-stream"

    try:
        handle = record.file.open("rb")
    except (FileNotFoundError, OSError):
        return Response({"detail": "文件已从磁盘移除。"}, status=404)

    response = FileResponse(
        handle,
        as_attachment=not inline,
        filename=record.original_name,
        content_type=content_type,
    )
    response.block_size = 64 * 1024
    response.streaming_content = stream_chunks(request, response.streaming_content)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response
