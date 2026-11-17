"""Private material library APIs: folders, materials, downloads and attachments."""
from __future__ import annotations

from pathlib import Path

from django.db.models import Max, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from accounts.permissions import CanUseWorkspace
from config.http import error, no_store, paginate, parse_int
from config.streaming import stream_chunks

from .library import (
    MaterialError,
    extension_of,
    is_previewable,
    safe_original_name,
    sha256_of,
    storage_name,
    validate_upload,
)
from .models import Folder, Material, Tag, Task, TaskMaterial
from .serializers import (
    FolderSerializer,
    MaterialSerializer,
    TaskMaterialSerializer,
)
from .views import serializer_error

MAX_REMARK_LENGTH = 500


def folder_queryset(request):
    queryset = Folder.objects.filter(owner=request.user)
    raw = request.query_params.get("deleted", "")
    if str(raw).lower() in {"1", "true", "yes"}:
        return queryset.filter(deleted_at__isnull=False)
    return queryset.filter(deleted_at__isnull=True)


def material_queryset(request):
    queryset = Material.objects.filter(owner=request.user)
    raw = request.query_params.get("deleted", "")
    if str(raw).lower() in {"1", "true", "yes"}:
        queryset = queryset.filter(deleted_at__isnull=False)
    else:
        queryset = queryset.filter(deleted_at__isnull=True)

    folder = request.query_params.get("folder")
    if folder:
        queryset = queryset.filter(folder_id=folder)
    tag = request.query_params.get("tag")
    if tag:
        queryset = queryset.filter(tags__id=tag)
    file_type = (request.query_params.get("type") or "").strip().lower()
    if file_type:
        queryset = queryset.filter(original_name__iendswith=file_type)
    keyword = (request.query_params.get("q") or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(original_name__icontains=keyword) | Q(remark__icontains=keyword)
        )
    created_after = request.query_params.get("created_after")
    if created_after:
        queryset = queryset.filter(created_at__date__gte=created_after)
    created_before = request.query_params.get("created_before")
    if created_before:
        queryset = queryset.filter(created_at__date__lte=created_before)
    return queryset.distinct()


def resolve_folder(owner, folder_id):
    if not folder_id:
        return None
    folder = Folder.objects.filter(pk=folder_id, owner=owner, deleted_at__isnull=True).first()
    if folder is None:
        raise MaterialError("资料夹不存在或不属于当前账号。", code="invalid_folder")
    return folder


def resolve_material_tags(owner, raw_tags):
    if not raw_tags:
        return []
    names = [str(item).strip() for item in raw_tags if str(item).strip()]
    tags = []
    for name in names:
        tag = Tag.objects.filter(owner=owner, normalized_name=name.casefold()).first()
        if tag is None:
            tag = Tag.objects.create(
                owner=owner, name=name[:64], normalized_name=name.casefold()[:64]
            )
        tags.append(tag)
    return tags


# --------------------------------------------------------------------------- #
# folders
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseWorkspace])
def folder_list(request):
    if request.method == "GET":
        queryset = folder_queryset(request).order_by("position", "created_at")
        return no_store(Response(paginate(queryset, request, FolderSerializer)))

    name = str(request.data.get("name") or "").strip()
    if not name:
        return error("资料夹名称不能为空。", 400, code="invalid_payload")
    if len(name) > 120:
        return error("资料夹名称不能超过 120 个字符。", 400, code="invalid_payload")
    highest = Folder.objects.filter(owner=request.user).aggregate(value=Max("position"))
    position = (highest["value"] or 0) + 1
    folder = Folder.objects.create(owner=request.user, name=name, position=position)
    return Response(FolderSerializer(folder).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseWorkspace])
def folder_detail(request, folder_id):
    folder = Folder.objects.filter(pk=folder_id, owner=request.user).first()
    if folder is None:
        return error("资料夹不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(FolderSerializer(folder).data))

    if request.method == "DELETE":
        if folder.deleted_at is None:
            Folder.objects.filter(pk=folder.pk).update(
                deleted_at=timezone.now(),
                version=folder.version + 1,
                updated_at=timezone.now(),
            )
            folder.refresh_from_db()
        return no_store(Response(FolderSerializer(folder).data))

    version = request.data.get("version")
    if version is None:
        return error("更新资料夹必须提交 version。", 400, code="version_required")
    name = str(request.data.get("name") or "").strip()
    if not name:
        return error("资料夹名称不能为空。", 400, code="invalid_payload")
    if len(name) > 120:
        return error("资料夹名称不能超过 120 个字符。", 400, code="invalid_payload")
    updated = Folder.objects.filter(
        pk=folder.pk, owner=request.user, version=version, deleted_at__isnull=True
    ).update(name=name, version=version + 1, updated_at=timezone.now())
    if not updated:
        current = Folder.objects.filter(pk=folder.pk, owner=request.user).first()
        return error(
            "资料夹已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=current.version if current else None,
        )
    folder.refresh_from_db()
    return no_store(Response(FolderSerializer(folder).data))


# --------------------------------------------------------------------------- #
# materials
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([CanUseWorkspace])
def material_list(request):
    if request.method == "GET":
        queryset = material_queryset(request).order_by("-created_at")
        return no_store(Response(paginate(queryset, request, MaterialSerializer)))

    upload = request.FILES.get("file")
    if upload is None:
        return error("请选择要上传的文件。", 400, code="missing_file")
    try:
        folder = resolve_folder(request.user, request.data.get("folder"))
        suffix, detected = validate_upload(upload)
    except MaterialError as exc:
        status = 413 if exc.code == "file_too_large" else 400
        return error(exc.detail, status, code=exc.code)

    remark = str(request.data.get("remark") or "").strip()[:MAX_REMARK_LENGTH]
    raw_tags = request.data.get("tags")
    tag_names = []
    if isinstance(raw_tags, str):
        tag_names = [item for item in raw_tags.replace("，", ",").split(",") if item.strip()]
    elif isinstance(raw_tags, (list, tuple)):
        tag_names = [str(item) for item in raw_tags if str(item).strip()]

    original_name = safe_original_name(upload.name)
    material = Material(
        owner=request.user,
        folder=folder,
        original_name=original_name,
        detected_mime=detected,
        remark=remark,
        source="desktop",
        state="ready",
    )
    material.storage_key.save(storage_name(suffix), upload, save=False)
    material.size_bytes = material.storage_key.size
    try:
        with material.storage_key.open("rb") as handle:
            material.sha256 = sha256_of(handle)
    except OSError:
        material.sha256 = ""
    material.save()
    tags = resolve_material_tags(request.user, tag_names)
    if tags:
        material.tags.set(tags)
    return Response(MaterialSerializer(material).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseWorkspace])
def material_detail(request, material_id):
    material = Material.objects.filter(pk=material_id, owner=request.user).first()
    if material is None:
        return error("资料不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(MaterialSerializer(material).data))

    if request.method == "DELETE":
        if material.deleted_at is None:
            Material.objects.filter(pk=material.pk).update(
                deleted_at=timezone.now(),
                version=material.version + 1,
                updated_at=timezone.now(),
            )
            material.refresh_from_db()
        return no_store(Response(MaterialSerializer(material).data))

    version = request.data.get("version")
    if version is None:
        return error("更新资料必须提交 version。", 400, code="version_required")
    fields: dict = {}
    if "remark" in request.data:
        fields["remark"] = str(request.data.get("remark") or "").strip()[:MAX_REMARK_LENGTH]
    if "original_name" in request.data:
        name = safe_original_name(request.data.get("original_name"))
        if not name:
            return error("文件名不能为空。", 400, code="invalid_payload")
        fields["original_name"] = name
    if "folder" in request.data:
        try:
            folder = resolve_folder(request.user, request.data.get("folder"))
        except MaterialError as exc:
            return error(exc.detail, 400, code=exc.code)
        fields["folder"] = folder

    updated = Material.objects.filter(
        pk=material.pk, owner=request.user, version=version, deleted_at__isnull=True
    ).update(version=version + 1, updated_at=timezone.now(), **fields)
    if not updated:
        current = Material.objects.filter(pk=material.pk, owner=request.user).first()
        return error(
            "资料已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=current.version if current else None,
        )
    material.refresh_from_db()
    return no_store(Response(MaterialSerializer(material).data))


@api_view(["POST"])
@permission_classes([CanUseWorkspace])
def material_restore(request, material_id):
    material = Material.objects.filter(pk=material_id, owner=request.user).first()
    if material is None:
        return error("资料不存在。", 404, code="not_found")
    if material.deleted_at is None:
        return no_store(Response(MaterialSerializer(material).data))
    Material.objects.filter(pk=material.pk, version=material.version).update(
        deleted_at=None, version=material.version + 1, updated_at=timezone.now()
    )
    material.refresh_from_db()
    return no_store(Response(MaterialSerializer(material).data))


@api_view(["GET"])
@permission_classes([CanUseWorkspace])
def material_download(request, material_id):
    material = Material.objects.filter(pk=material_id, owner=request.user).first()
    if material is None:
        return error("资料不存在。", 404, code="not_found")
    if material.deleted_at is not None:
        return error("资料已移入回收站。", 404, code="deleted")
    if not material.storage_key:
        return error("资料文件不存在。", 404, code="not_found")

    inline = (
        request.query_params.get("inline") in {"1", "true"}
        and is_previewable(material.original_name)
    )
    try:
        handle = material.storage_key.open("rb")
    except (FileNotFoundError, OSError):
        return error("资料文件已从磁盘移除。", 404, code="not_found")

    response = FileResponse(
        handle,
        as_attachment=not inline,
        filename=material.original_name,
        content_type=material.detected_mime if inline else "application/octet-stream",
    )
    response.block_size = 64 * 1024
    response.streaming_content = stream_chunks(request, response.streaming_content)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response


# --------------------------------------------------------------------------- #
# task attachments
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseWorkspace])
def task_materials(request, task_id):
    task = Task.objects.filter(pk=task_id, owner=request.user, deleted_at__isnull=True).first()
    if task is None:
        return error("任务不存在。", 404, code="not_found")

    if request.method == "GET":
        links = TaskMaterial.objects.filter(task=task).select_related("material")
        materials = [link.material for link in links if link.material.deleted_at is None]
        return no_store(Response(MaterialSerializer(materials, many=True).data))

    material_id = request.data.get("material")
    material = Material.objects.filter(pk=material_id, owner=request.user).first()
    if material is None:
        return error("资料不存在或不属于当前账号。", 404, code="not_found")
    link, created = TaskMaterial.objects.get_or_create(task=task, material=material)
    if not created and link.deleted_at is not None:
        link.deleted_at = None
        link.version += 1
        link.save()
    payload = TaskMaterialSerializer(link).data
    return Response(payload, status=201 if created else 200)


@api_view(["DELETE"])
@permission_classes([CanUseWorkspace])
def task_material_detail(request, task_id, material_id):
    task = Task.objects.filter(pk=task_id, owner=request.user).first()
    material = Material.objects.filter(pk=material_id, owner=request.user).first()
    if task is None or material is None:
        return error("任务或资料不存在。", 404, code="not_found")
    TaskMaterial.objects.filter(task=task, material=material).delete()
    return Response(status=204)
