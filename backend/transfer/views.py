from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.logging import client_ip
from accounts.logging import record as audit_log
from config.streaming import stream_chunks
from .models import AnnouncementHistory, TransferAnnouncement, TransferFile
from .permissions import IsTransferAdmin, is_transfer_admin
from .serializers import TransferFileSerializer

MAX_TRANSFER_BYTES = 1024 * 1024 * 1024
# The station list keeps a plain array for the existing client, but the number
# of rows is bounded so that a large table cannot produce an unbounded answer.
MAX_TRANSFER_LIST_ROWS = 200
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


def _budget_counters(request) -> tuple[str, str]:
    key = _budget_key(request)
    return f"{key}:bytes", f"{key}:files"


def _decrement(cache_key: str, amount: int) -> None:
    """Give a reservation back; a vanished key needs no correction."""
    try:
        cache.incr(cache_key, -amount)
    except ValueError:
        pass


def reserve_anonymous_upload(request, size: int) -> Response | None:
    """Reserve budget for an anonymous upload before the file is stored.

    The public transfer station accepts files without an account, so it needs
    a total budget and a request rate limit: otherwise anonymous uploads can
    fill the disk.  The counters are increased before the file is written, so
    two concurrent uploads cannot both pass the limit, and a rejected upload
    gives the reservation back.
    """
    total_budget = anonymous_upload_budget()
    file_budget = anonymous_upload_rate_limit()
    if not total_budget and not file_budget:
        return None
    window = anonymous_upload_window()
    bytes_key, files_key = _budget_counters(request)
    for counter in (bytes_key, files_key):
        cache.add(counter, 0, timeout=window)
    try:
        used_bytes = cache.incr(bytes_key, size)
    except ValueError:
        used_bytes = size
    try:
        used_files = cache.incr(files_key, 1)
    except ValueError:
        used_files = 1
    if total_budget and used_bytes > total_budget:
        _decrement(bytes_key, size)
        _decrement(files_key, 1)
        return Response(
            {"detail": "免密上传总量已达上限，请稍后再试。"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if file_budget and used_files > file_budget:
        _decrement(bytes_key, size)
        _decrement(files_key, 1)
        return Response(
            {"detail": "免密上传次数已达上限，请稍后再试。"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


def release_anonymous_upload(request, size: int) -> None:
    """Give back a reservation when the upload did not reach the database."""
    bytes_key, files_key = _budget_counters(request)
    _decrement(bytes_key, size)
    _decrement(files_key, 1)


def parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "public", "公开"}


def safe_original_name(raw: str) -> str:
    name = Path(str(raw or "").replace("\\", "/")).name.strip()
    name = name.replace("\x00", "")
    # Windows silently drops trailing dots and spaces, so "payload.exe " would
    # be stored as "payload.exe".  Removing them keeps the stored name equal
    # to the checked name.
    name = name.rstrip(". ")
    return (name or "未命名文件")[:255]


def blocked_suffix(original_name: str) -> str:
    """The extension of a name after the trailing dots and spaces are gone."""
    return Path(original_name.strip().rstrip(". ")).suffix.lower()


def inferred_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([AllowAny])
def files(request):
    if request.method == "GET":
        queryset = TransferFile.objects.all()
        if not is_transfer_admin(request.user):
            queryset = queryset.filter(Q(visible_until__isnull=True) | Q(visible_until__gt=timezone.now()))
        if is_transfer_admin(request.user):
            pass  # Admin sees everything, including private drops.
        else:
            # Private drops contain administrator-only data, including their
            # metadata. Uploaders do not get a private-file exception.
            queryset = queryset.filter(is_public=True)
        # The response stays a plain list for the existing client, but the
        # number of rows is bounded so that a large table cannot produce an
        # unbounded response.
        rows = list(queryset[:MAX_TRANSFER_LIST_ROWS])
        return Response(
            TransferFileSerializer(rows, many=True).data,
            headers={"Cache-Control": "private, no-store"},
        )

    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "请选择要上传的文件。"}, status=400)
    if upload.size <= 0:
        return Response({"detail": "不能上传空文件。"}, status=400)
    if upload.size > MAX_TRANSFER_BYTES:
        return Response({"detail": "文件超过 1 GB 限制。"}, status=413)

    original_name = safe_original_name(upload.name or "未命名文件")
    suffix = blocked_suffix(original_name)
    if suffix in BLOCKED_EXTENSIONS:
        return Response(
            {"detail": "出于安全考虑，暂不支持上传可执行文件或脚本。"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    owner = request.user if request.user.is_authenticated else None
    reserved = 0
    if owner is None:
        # Anonymous uploads share a public budget so that they cannot fill
        # the disk of the server.  The budget is reserved before the file is
        # written, so concurrent uploads cannot slip past the limit.
        budget_error = reserve_anonymous_upload(request, upload.size)
        if budget_error is not None:
            return budget_error
        reserved = upload.size

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
    try:
        record.file.save(original_name, upload, save=False)
        record.save()
    except Exception:
        # The upload did not reach the database: give the budget back and
        # remove the partially written file instead of leaving it behind.
        if reserved:
            release_anonymous_upload(request, reserved)
        try:
            record.file.delete(save=False)
        except Exception:  # pragma: no cover - best effort cleanup
            pass
        raise
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
    if "visible_until" in request.data:
        raw_expiry = request.data.get("visible_until")
        if raw_expiry in (None, ""):
            record.visible_until = None
        else:
            parsed = parse_datetime(str(raw_expiry))
            if parsed is None:
                return Response({"detail": "可见截止时间格式无效。"}, status=400)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            record.visible_until = parsed
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
    if record.visible_until and record.visible_until <= timezone.now():
        return Response({"detail": "该文件的可见时效已结束。"}, status=410)
    if not record.is_public and not is_transfer_admin(request.user):
        return Response(
            {"detail": "该文件为私密投递，仅最高管理员可以下载。"},
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


def record_announcement_history(kind: str, content: str, actor) -> None:
    """Store a newly published announcement; withdrawals are not history."""
    content = content.strip()
    if not content:
        return
    AnnouncementHistory.objects.create(
        kind=kind,
        content=content,
        published_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


@api_view(["GET", "PUT"])
@permission_classes([AllowAny])
def announcement(request):
    if request.method == "GET":
        item = TransferAnnouncement.objects.order_by("-updated_at").first()
        return Response({"content": item.content if item else "", "updated_at": item.updated_at if item else None})
    if not is_transfer_admin(request.user):
        return Response({"detail": "仅最高管理员可以发布公告。"}, status=403)
    content = str(request.data.get("content") or "").strip()
    if len(content) > 5000:
        return Response({"detail": "公告不能超过 5000 个字符。"}, status=400)
    item, _ = TransferAnnouncement.objects.get_or_create(pk=1)
    previous = item.content
    item.content = content
    item.updated_by = request.user
    item.save(update_fields=["content", "updated_by", "updated_at"])
    if content and content != previous:
        record_announcement_history(AnnouncementHistory.KIND_TRANSFER, content, request.user)
    return Response({"content": item.content, "updated_at": item.updated_at})


@api_view(["GET", "PUT"])
@permission_classes([AllowAny])
def login_announcement(request):
    """Public login-page notice; only the highest administrator may edit it."""
    item = TransferAnnouncement.objects.order_by("-updated_at").first()
    if request.method == "GET":
        return Response(
            {
                "content": item.login_content if item else "",
                "updated_at": item.login_updated_at if item else None,
            },
            headers={"Cache-Control": "no-store"},
        )
    if not is_transfer_admin(request.user):
        return Response({"detail": "仅最高管理员可以发布登录页公告。"}, status=403)
    content = str(request.data.get("content") or "").strip()
    if len(content) > 5000:
        return Response({"detail": "公告不能超过 5000 个字符。"}, status=400)
    item, _ = TransferAnnouncement.objects.get_or_create(pk=1)
    previous = item.login_content
    item.login_content = content
    item.login_updated_at = timezone.now()
    item.updated_by = request.user
    item.save(
        update_fields=[
            "login_content",
            "login_updated_at",
            "updated_by",
            "updated_at",
        ]
    )
    if content and content != previous:
        record_announcement_history(AnnouncementHistory.KIND_LOGIN, content, request.user)
    audit_log(
        request,
        "login_announcement_update",
        user=request.user,
        detail="published" if content else "withdrawn",
    )
    return Response(
        {"content": item.login_content, "updated_at": item.login_updated_at}
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def announcement_history(request):
    """Public announcement history, newest first."""
    kind = str(request.query_params.get("kind") or "").strip()
    queryset = AnnouncementHistory.objects.all()
    if kind in {
        AnnouncementHistory.KIND_TRANSFER,
        AnnouncementHistory.KIND_LOGIN,
    }:
        queryset = queryset.filter(kind=kind)
    rows = queryset[:50]
    return Response(
        [
            {
                "id": row.id,
                "kind": row.kind,
                "content": row.content,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        headers={"Cache-Control": "no-store"},
    )
