"""Phone upload APIs.

Desktop owner endpoints manage the session; the phone endpoints only deliver
files into the session they were given.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import AccountSecurity
from config.http import error, no_store

from .library import MaterialError, safe_original_name, sha256_of, storage_name, validate_upload
from .models import Folder, Material, Task, TaskMaterial, UploadReceipt, UploadSession
from .serializers import MaterialSerializer
from .upload_auth import UploadSessionAuthentication


def public_base_url(request) -> str:
    """Only an explicitly configured address is trusted for QR codes."""
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL
    if settings.DEBUG:
        return request.build_absolute_uri("/").rstrip("/")
    return ""


def serialize_session(session: UploadSession) -> dict:
    return {
        "id": str(session.id),
        "state": session.state,
        "expires_at": session.expires_at.isoformat(),
        "created_at": session.created_at.isoformat(),
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "quota": {
            "max_files": session.max_files,
            "max_bytes": session.max_bytes,
            "max_file_bytes": session.max_file_bytes,
            "reserved_files": session.reserved_files,
            "reserved_bytes": session.reserved_bytes,
            "committed_files": session.committed_files,
            "committed_bytes": session.committed_bytes,
        },
        "destination": {
            "folder_id": str(session.destination_folder_id) if session.destination_folder_id else None,
            "folder_name": session.destination_folder.name if session.destination_folder_id else "",
            "task_id": str(session.destination_task_id) if session.destination_task_id else None,
            "task_title": session.destination_task.title if session.destination_task_id else "",
        },
    }


def serialize_receipt(receipt: UploadReceipt) -> dict:
    return {
        "id": str(receipt.id),
        "client_upload_id": receipt.client_upload_id,
        "original_name": receipt.original_name,
        "declared_size": receipt.declared_size,
        "actual_size": receipt.actual_size,
        "sha256": receipt.sha256,
        "state": receipt.state,
        "failure_code": receipt.failure_code,
        "material_id": str(receipt.material_id) if receipt.material_id else None,
        "created_at": receipt.created_at.isoformat(),
        "updated_at": receipt.updated_at.isoformat(),
    }


def revoke_session(session: UploadSession) -> None:
    now = timezone.now()
    UploadSession.objects.filter(pk=session.pk).update(
        state="revoked", revoked_at=now
    )
    receipts = session.receipts.filter(state__in=["reserved", "receiving"])
    for receipt in receipts:
        receipt.state = "expired"
        receipt.failure_code = "session_revoked"
        receipt.save(update_fields=["state", "failure_code", "updated_at"])
    UploadSession.objects.filter(pk=session.pk).update(
        reserved_files=0, reserved_bytes=0, used_bytes=F("committed_bytes")
    )
    session.refresh_from_db()


# --------------------------------------------------------------------------- #
# owner endpoints
# --------------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def session_create(request):
    folder = None
    task = None
    folder_id = request.data.get("folder")
    task_id = request.data.get("task")
    if folder_id:
        folder = Folder.objects.filter(
            pk=folder_id, owner=request.user, deleted_at__isnull=True
        ).first()
        if folder is None:
            return error("资料夹不存在或不属于当前账号。", 400, code="invalid_reference")
    if task_id:
        task = Task.objects.filter(
            pk=task_id, owner=request.user, deleted_at__isnull=True
        ).first()
        if task is None:
            return error("任务不存在或不属于当前账号。", 400, code="invalid_reference")

    now = timezone.now()
    max_active = getattr(settings, "UPLOAD_SESSION_MAX_ACTIVE", 3)
    active = UploadSession.objects.filter(
        owner=request.user, state="active", expires_at__gt=now
    ).order_by("created_at")
    while active.count() >= max_active:
        oldest = active.first()
        if oldest is None:
            break
        revoke_session(oldest)

    raw_token = secrets.token_urlsafe(32)
    session = UploadSession.objects.create(
        owner=request.user,
        token_digest=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        destination_folder=folder,
        destination_task=task,
        expires_at=now + timedelta(
            seconds=getattr(settings, "UPLOAD_SESSION_TTL_SECONDS", 600)
        ),
        max_files=getattr(settings, "UPLOAD_SESSION_MAX_FILES", 20),
        max_bytes=getattr(settings, "UPLOAD_SESSION_MAX_BYTES", 500 * 1024 * 1024),
        max_file_bytes=getattr(
            settings, "UPLOAD_SESSION_MAX_FILE_BYTES", 100 * 1024 * 1024
        ),
        auth_version=AccountSecurity.version_for(request.user),
    )

    base = public_base_url(request)
    payload = serialize_session(session)
    payload["token"] = raw_token
    payload["qr_payload"] = f"{base}/upload#session={session.id}&token={raw_token}" if base else ""
    payload["qr_warning"] = (
        ""
        if base
        else "尚未配置 PUBLIC_BASE_URL，二维码无法被手机访问；请在环境变量中设置公开地址。"
    )
    return Response(payload, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_status(request, session_id):
    session = UploadSession.objects.filter(pk=session_id, owner=request.user).first()
    if session is None:
        return error("上传会话不存在。", 404, code="not_found")
    payload = serialize_session(session)
    receipts = session.receipts.order_by("created_at")
    payload["receipts"] = [serialize_receipt(receipt) for receipt in receipts]
    payload["materials"] = MaterialSerializer(
        [receipt.material for receipt in receipts if receipt.material_id], many=True
    ).data
    return no_store(Response(payload))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def session_revoke(request, session_id):
    session = UploadSession.objects.filter(pk=session_id, owner=request.user).first()
    if session is None:
        return error("上传会话不存在。", 404, code="not_found")
    if session.state == "active":
        revoke_session(session)
    return no_store(Response(serialize_session(session)))


# --------------------------------------------------------------------------- #
# phone endpoints
# --------------------------------------------------------------------------- #
def session_guard(request):
    """Return the session when it is still usable, otherwise a DRF error."""
    session = request.upload_session
    if session.state != "active":
        return error("上传会话已结束。", 403, code="session_closed")
    if session.expires_at <= timezone.now():
        return error("上传会话已过期。", 403, code="session_expired")
    if AccountSecurity.version_for(session.owner) != session.auth_version:
        return error("账号安全状态已变化，上传会话失效。", 403, code="auth_version_mismatch")
    return None


@api_view(["GET"])
@authentication_classes([UploadSessionAuthentication])
@permission_classes([IsAuthenticated])
def session_info(request):
    """The phone reads its own session limits without touching owner data."""
    guard = session_guard(request)
    if guard is not None:
        return guard
    session = request.upload_session
    payload = serialize_session(session)
    payload["receipts"] = [
        serialize_receipt(receipt)
        for receipt in session.receipts.filter(state__in=["committed", "failed"])
    ]
    return no_store(Response(payload))


@api_view(["POST"])
@authentication_classes([UploadSessionAuthentication])
@permission_classes([IsAuthenticated])
def receipt_prepare(request):
    guard = session_guard(request)
    if guard is not None:
        return guard
    session = request.upload_session

    client_upload_id = str(request.data.get("client_upload_id") or "").strip()
    original_name = safe_original_name(request.data.get("original_name") or "")
    try:
        declared_size = int(request.data.get("declared_size"))
    except (TypeError, ValueError):
        return error("declared_size 必须是整数。", 400, code="invalid_payload")
    if not client_upload_id or len(client_upload_id) > 64:
        return error("client_upload_id 无效。", 400, code="invalid_payload")
    if declared_size <= 0:
        return error("文件大小无效。", 400, code="invalid_payload")
    if declared_size > session.max_file_bytes:
        return error(
            "文件超过单文件上限。", 413, code="file_too_large"
        )

    try:
        from .library import validate_extension

        validate_extension(original_name)
    except MaterialError as exc:
        return error(exc.detail, 400, code=exc.code)

    existing = UploadReceipt.objects.filter(
        session=session, client_upload_id=client_upload_id
    ).first()
    if existing is not None:
        if (
            existing.original_name != original_name
            or existing.declared_size != declared_size
        ):
            return error(
                "同一请求标识的文件信息与已有收据不一致。",
                409,
                code="receipt_conflict",
                receipt=serialize_receipt(existing),
            )
        return Response(serialize_receipt(existing))

    now = timezone.now()
    reserved = UploadSession.objects.filter(
        pk=session.pk,
        state="active",
        expires_at__gt=now,
        reserved_files__lt=F("max_files"),
        used_bytes__lte=F("max_bytes") - declared_size,
    ).update(
        reserved_files=F("reserved_files") + 1,
        reserved_bytes=F("reserved_bytes") + declared_size,
        used_bytes=F("used_bytes") + declared_size,
    )
    if not reserved:
        return error("上传配额不足或会话已结束。", 409, code="quota_exceeded")

    try:
        with transaction.atomic():
            receipt = UploadReceipt.objects.create(
                session=session,
                client_upload_id=client_upload_id,
                original_name=original_name,
                declared_size=declared_size,
                state="reserved",
                lease_expires_at=now
                + timedelta(
                    seconds=getattr(settings, "UPLOAD_RECEIPT_LEASE_SECONDS", 1200)
                ),
            )
    except IntegrityError:
        UploadSession.objects.filter(pk=session.pk).update(
            reserved_files=F("reserved_files") - 1,
            reserved_bytes=F("reserved_bytes") - declared_size,
            used_bytes=F("used_bytes") - declared_size,
        )
        existing = UploadReceipt.objects.filter(
            session=session, client_upload_id=client_upload_id
        ).first()
        if existing is None:
            return error("创建上传收据失败，请重试。", 409, code="receipt_conflict")
        return Response(serialize_receipt(existing))

    return Response(serialize_receipt(receipt), status=201)


@api_view(["GET"])
@authentication_classes([UploadSessionAuthentication])
@permission_classes([IsAuthenticated])
def receipt_status(request, receipt_id):
    session = request.upload_session
    receipt = UploadReceipt.objects.filter(pk=receipt_id, session=session).first()
    if receipt is None:
        return error("上传收据不存在。", 404, code="not_found")
    return no_store(Response(serialize_receipt(receipt)))


@api_view(["POST"])
@authentication_classes([UploadSessionAuthentication])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def receipt_content(request, receipt_id):
    guard = session_guard(request)
    if guard is not None:
        return guard
    session = request.upload_session
    receipt = UploadReceipt.objects.filter(pk=receipt_id, session=session).first()
    if receipt is None:
        return error("上传收据不存在。", 404, code="not_found")

    if receipt.state == "committed":
        payload = serialize_receipt(receipt)
        payload["material"] = MaterialSerializer(receipt.material).data
        return Response(payload)

    upload = request.FILES.get("file")
    if upload is None:
        return error("请选择要上传的文件。", 400, code="missing_file")

    now = timezone.now()
    attempt_id = uuid.uuid4()
    claimed = UploadReceipt.objects.filter(pk=receipt.pk, state="reserved").update(
        state="receiving",
        attempt_id=attempt_id,
        lease_expires_at=now
        + timedelta(
            seconds=getattr(settings, "UPLOAD_RECEIPT_LEASE_SECONDS", 1200)
        ),
        updated_at=now,
    )
    if not claimed:
        receipt.refresh_from_db()
        if receipt.state == "committed":
            payload = serialize_receipt(receipt)
            payload["material"] = MaterialSerializer(receipt.material).data
            return Response(payload)
        return error("该文件正在接收中或已结束。", 409, code="receipt_busy")

    def release_reservation(extra_bytes: int = 0) -> None:
        UploadSession.objects.filter(pk=session.pk).update(
            reserved_files=F("reserved_files") - 1,
            reserved_bytes=F("reserved_bytes") - receipt.declared_size,
            used_bytes=F("used_bytes") - receipt.declared_size + extra_bytes,
        )

    def fail(code: str, status: int = 400):
        receipt.state = "failed"
        receipt.failure_code = code
        receipt.save(update_fields=["state", "failure_code", "updated_at"])
        release_reservation()
        return error(code, status, code=code)

    try:
        suffix, detected = validate_upload(upload)
    except MaterialError as exc:
        status = 413 if exc.code == "file_too_large" else 400
        return fail(exc.code if exc.code != "invalid_file" else "invalid_file", status)

    actual_size = upload.size
    if actual_size > receipt.declared_size:
        return fail("size_mismatch", 400)
    if actual_size > session.max_file_bytes:
        return fail("file_too_large", 413)

    try:
        upload.seek(0)
        digest = sha256_of(upload)
        upload.seek(0)
    except (AttributeError, ValueError, OSError):
        return fail("read_failed", 400)

    # The destination is validated again right before the final commit.
    folder = session.destination_folder
    if folder is not None and (
        folder.deleted_at is not None
        or folder.owner_id != session.owner_id
    ):
        return fail("target_unavailable", 409)
    task = session.destination_task
    if task is not None and (
        task.deleted_at is not None or task.owner_id != session.owner_id
    ):
        return fail("target_unavailable", 409)
    if AccountSecurity.version_for(session.owner) != session.auth_version:
        return fail("auth_version_mismatch", 403)

    material = Material(
        owner=session.owner,
        folder=folder,
        original_name=receipt.original_name,
        detected_mime=detected,
        remark="手机扫码上传",
        source="qr",
        state="ready",
    )
    material.storage_key.save(storage_name(suffix), upload, save=False)
    material.size_bytes = material.storage_key.size
    material.sha256 = digest

    try:
        with transaction.atomic():
            material.save()
            if task is not None:
                TaskMaterial.objects.get_or_create(task=task, material=material)
            UploadReceipt.objects.filter(pk=receipt.pk, attempt_id=attempt_id).update(
                state="committed",
                actual_size=actual_size,
                sha256=digest,
                material=material,
                failure_code="",
                updated_at=timezone.now(),
            )
            UploadSession.objects.filter(pk=session.pk).update(
                reserved_files=F("reserved_files") - 1,
                reserved_bytes=F("reserved_bytes") - receipt.declared_size,
                committed_files=F("committed_files") + 1,
                committed_bytes=F("committed_bytes") + actual_size,
                used_bytes=F("used_bytes") - receipt.declared_size + actual_size,
            )
    except IntegrityError:
        return fail("commit_failed", 409)

    receipt.refresh_from_db()
    payload = serialize_receipt(receipt)
    payload["material"] = MaterialSerializer(material).data
    return Response(payload, status=201)
