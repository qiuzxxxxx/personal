"""Workspace APIs: today view, tasks, projects, tags and daily entries.

Every view is owner scoped. The owner always comes from the request token.
"""
from __future__ import annotations

import zoneinfo
from datetime import date as date_cls
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.utils import timezone as django_timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import CanUseWorkspace
from config.http import BadRequest, error, no_store, paginate, parse_date

from .models import (
    OPEN_TASK_STATUSES,
    DailyEntry,
    Project,
    Tag,
    Task,
    WorkspacePreference,
    normalize_tag_name,
)
from .serializers import (
    DailyEntrySerializer,
    DailyEntryWriteSerializer,
    ProjectPatchSerializer,
    ProjectSerializer,
    ProjectWriteSerializer,
    TagPatchSerializer,
    TagSerializer,
    TagWriteSerializer,
    TaskPatchSerializer,
    TaskSerializer,
    TaskWriteSerializer,
)

DEFAULT_TIMEZONE = "Asia/Shanghai"
WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def user_timezone(user):
    preference = getattr(user, "workspace_preference", None)
    name = preference.timezone if preference else DEFAULT_TIMEZONE
    try:
        return zoneinfo.ZoneInfo(name)
    except Exception:
        return zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)


def local_today(user) -> date_cls:
    return datetime.now(user_timezone(user)).date()


def parse_day(value: str) -> date_cls:
    try:
        return date_cls.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise BadRequest("date 必须是 YYYY-MM-DD 格式。") from None


def serializer_error(serializer) -> Response:
    detail = serializer.errors
    first = ""
    if isinstance(detail, dict):
        for key, value in detail.items():
            if isinstance(value, (list, tuple)) and value:
                first = f"{key}: {value[0]}"
                break
            first = str(value)
            break
    elif isinstance(detail, (list, tuple)) and detail:
        first = str(detail[0])
    return error(first or "请求参数无效。", 400, code="invalid_payload")


def serialize_preference(user) -> dict:
    preference, _ = WorkspacePreference.objects.get_or_create(user=user)
    return {
        "id": str(preference.id),
        "timezone": preference.timezone,
        "week_starts_on": preference.week_starts_on,
        "default_task_priority": preference.default_task_priority,
    }


def owner_queryset(request, model):
    return model.objects.filter(owner=request.user)


def visible_queryset(request, model):
    """Active records of the owner; ``?deleted=true`` returns the trash."""
    queryset = owner_queryset(request, model)
    raw = request.query_params.get("deleted", "")
    if str(raw).lower() in {"1", "true", "yes"}:
        return queryset.filter(deleted_at__isnull=False)
    return queryset.filter(deleted_at__isnull=True)


def task_queryset(request):
    queryset = visible_queryset(request, Task)
    scheduled = request.query_params.get("scheduled_date")
    if scheduled not in (None, ""):
        queryset = queryset.filter(scheduled_date=parse_day(scheduled))
    status = request.query_params.get("status")
    if status:
        wanted = [item for item in status.split(",") if item]
        queryset = queryset.filter(status__in=wanted)
    project = request.query_params.get("project")
    if project:
        queryset = queryset.filter(project_id=project)
    tag = request.query_params.get("tag")
    if tag:
        queryset = queryset.filter(tags__id=tag)
    keyword = (request.query_params.get("q") or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword) | Q(description__icontains=keyword)
        )
    return queryset.distinct()


def resolve_project(owner, project_id):
    if not project_id:
        return None
    project = Project.objects.filter(pk=project_id, owner=owner).first()
    if project is None:
        raise BadRequest("项目不存在或不属于当前账号。")
    return project


def resolve_tags(owner, tag_ids):
    if not tag_ids:
        return []
    unique_ids = []
    for raw in tag_ids:
        value = str(raw)
        if value and value not in unique_ids:
            unique_ids.append(value)
    tags = list(Tag.objects.filter(id__in=unique_ids, owner=owner, deleted_at__isnull=True))
    if len(tags) != len(unique_ids):
        raise BadRequest("标签不存在或不属于当前账号。")
    return tags


def next_task_position(owner) -> int:
    highest = Task.objects.filter(owner=owner).aggregate(value=Max("position"))["value"]
    return 0 if highest is None else highest + 1


def task_payload_signature(data: dict) -> tuple:
    return (
        (data.get("title") or "").strip(),
        data.get("description") or "",
        data.get("status") or "todo",
        data.get("priority") or "normal",
        str(data.get("scheduled_date") or ""),
        str(data.get("due_at") or ""),
        str(data.get("project") or ""),
        tuple(sorted(str(item) for item in (data.get("tags") or []))),
    )


def apply_status_fields(task: Task, status: str) -> dict:
    """Return the scalar changes implied by a status transition."""
    fields: dict = {}
    if status == "done":
        # Re-completing a task keeps the original completion time.
        if task.completed_at is None:
            fields["completed_at"] = django_timezone.now()
    else:
        fields["completed_at"] = None
    return fields


# --------------------------------------------------------------------------- #
# today / preferences
# --------------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([CanUseWorkspace])
def today(request):
    user = request.user
    tz = user_timezone(user)
    raw = request.query_params.get("date")
    day = parse_day(raw) if raw else datetime.now(tz).date()
    now = django_timezone.now()

    scheduled = list(
        Task.objects.filter(
            owner=user, deleted_at__isnull=True, scheduled_date=day
        ).order_by("position", "created_at")
    )
    overdue = list(
        Task.objects.filter(
            owner=user,
            deleted_at__isnull=True,
            status__in=OPEN_TASK_STATUSES,
            due_at__isnull=False,
            due_at__lt=now,
        ).order_by("due_at")
    )
    needs_reschedule = Task.objects.filter(
        owner=user,
        deleted_at__isnull=True,
        status__in=OPEN_TASK_STATUSES,
        scheduled_date__lt=day,
    ).count()
    unscheduled = Task.objects.filter(
        owner=user,
        deleted_at__isnull=True,
        status__in=OPEN_TASK_STATUSES,
        scheduled_date__isnull=True,
    ).count()

    start = django_timezone.make_aware(datetime.combine(day, time.min), tz)
    end = start + timedelta(days=1)
    completed_today = Task.objects.filter(
        owner=user,
        deleted_at__isnull=True,
        status="done",
        completed_at__gte=start,
        completed_at__lt=end,
    ).count()

    entry = DailyEntry.objects.filter(owner=user, date=day).first()
    journal = None
    if entry is not None:
        journal = {
            "id": str(entry.id),
            "date": entry.date.isoformat(),
            "version": entry.version,
            "content": entry.content,
            "summary": entry.content[:120],
            "updated_at": entry.updated_at.isoformat(),
        }

    payload = {
        "date": day.isoformat(),
        "weekday": WEEKDAY_NAMES[day.weekday()],
        "timezone": str(tz),
        "tasks": TaskSerializer(scheduled, many=True).data,
        "overdue": TaskSerializer(overdue, many=True).data,
        "overdue_count": len(overdue),
        "needs_reschedule_count": needs_reschedule,
        "unscheduled_count": unscheduled,
        "completed_today": completed_today,
        "journal": journal,
    }
    return no_store(Response(payload))


@api_view(["GET", "PATCH"])
@permission_classes([CanUseWorkspace])
def preferences(request):
    if request.method == "GET":
        return no_store(Response(serialize_preference(request.user)))

    data = request.data if isinstance(request.data, dict) else {}
    timezone_name = str(data.get("timezone") or "").strip() or DEFAULT_TIMEZONE
    try:
        zoneinfo.ZoneInfo(timezone_name)
    except Exception:
        return error("timezone 必须是有效的 IANA 时区标识。", 400, code="invalid_timezone")
    priority = str(data.get("default_task_priority") or "normal")
    if priority not in {"low", "normal", "high"}:
        return error("default_task_priority 取值无效。", 400, code="invalid_priority")
    try:
        week_starts_on = int(data.get("week_starts_on", 1))
    except (TypeError, ValueError):
        return error("week_starts_on 必须是整数。", 400, code="invalid_week_start")
    if week_starts_on not in {0, 1, 6}:
        return error("week_starts_on 取值无效。", 400, code="invalid_week_start")

    preference, _ = WorkspacePreference.objects.get_or_create(user=request.user)
    preference.timezone = timezone_name
    preference.week_starts_on = week_starts_on
    preference.default_task_priority = priority
    preference.save(
        update_fields=["timezone", "week_starts_on", "default_task_priority", "updated_at"]
    )
    return no_store(Response(serialize_preference(request.user)))


# --------------------------------------------------------------------------- #
# tasks
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseWorkspace])
def task_list(request):
    if request.method == "GET":
        queryset = task_queryset(request).order_by("position", "created_at")
        return no_store(Response(paginate(queryset, request, TaskSerializer)))

    serializer = TaskWriteSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data

    client_request_id = (data.get("client_request_id") or "").strip()
    if client_request_id:
        existing = Task.objects.filter(
            owner=request.user, client_request_id=client_request_id
        ).first()
        if existing is not None:
            if task_payload_signature(data) == task_payload_signature(
                {
                    "title": existing.title,
                    "description": existing.description,
                    "status": existing.status,
                    "priority": existing.priority,
                    "scheduled_date": existing.scheduled_date,
                    "due_at": existing.due_at,
                    "project": existing.project_id,
                    "tags": [tag.id for tag in existing.tags.all()],
                }
            ):
                return no_store(Response(TaskSerializer(existing).data))
            return error(
                "同一请求标识已用于其他任务内容。",
                409,
                code="client_request_id_conflict",
                current_version=existing.version,
            )

    try:
        project = resolve_project(request.user, data.get("project"))
        tags = resolve_tags(request.user, data.get("tags"))
    except BadRequest as exc:
        return error(str(exc), 400, code="invalid_reference")

    now = django_timezone.now()
    status = data.get("status") or "todo"
    task = Task(
        owner=request.user,
        project=project,
        title=data["title"],
        description=data.get("description") or "",
        status=status,
        priority=data.get("priority") or "normal",
        scheduled_date=data.get("scheduled_date"),
        due_at=data.get("due_at"),
        client_request_id=client_request_id,
        position=next_task_position(request.user),
    )
    if status == "done":
        task.completed_at = now
    try:
        with transaction.atomic():
            task.save()
            if tags:
                task.tags.set(tags)
    except IntegrityError:
        return error("任务创建冲突，请刷新后重试。", 409, code="create_conflict")
    return Response(TaskSerializer(task).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseWorkspace])
def task_detail(request, task_id):
    task = Task.objects.filter(pk=task_id, owner=request.user).first()
    if task is None:
        return error("任务不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(TaskSerializer(task).data))

    if request.method == "DELETE":
        if task.deleted_at is not None:
            return no_store(Response(TaskSerializer(task).data))
        Task.objects.filter(pk=task.pk).update(
            deleted_at=django_timezone.now(),
            version=task.version + 1,
            updated_at=django_timezone.now(),
        )
        task.refresh_from_db()
        return no_store(Response(TaskSerializer(task).data))

    serializer = TaskPatchSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data
    version = data.get("version")
    if version is None:
        return error("更新任务必须提交 version。", 400, code="version_required")

    try:
        project = (
            resolve_project(request.user, data.get("project"))
            if "project" in data
            else None
        )
        tags = resolve_tags(request.user, data.get("tags")) if "tags" in data else None
    except BadRequest as exc:
        return error(str(exc), 400, code="invalid_reference")

    fields: dict = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "description" in data:
        fields["description"] = data.get("description") or ""
    if "priority" in data:
        fields["priority"] = data["priority"]
    if "scheduled_date" in data:
        fields["scheduled_date"] = data.get("scheduled_date")
    if "due_at" in data:
        fields["due_at"] = data.get("due_at")
    if "project" in data:
        fields["project"] = project
    if "status" in data:
        fields["status"] = data["status"]
        fields.update(apply_status_fields(task, data["status"]))

    now = django_timezone.now()
    with transaction.atomic():
        updated = Task.objects.filter(
            pk=task.pk, owner=request.user, version=version, deleted_at__isnull=True
        ).update(version=version + 1, updated_at=now, **fields)
        if not updated:
            current = Task.objects.filter(pk=task.pk, owner=request.user).first()
            if current is None:
                return error("任务不存在。", 404, code="not_found")
            return error(
                "任务已被其他设备修改，请刷新后重试。",
                409,
                code="version_conflict",
                current_version=current.version,
                current=TaskSerializer(current).data,
            )
        if "tags" in data:
            task.tags.set(tags)
    task.refresh_from_db()
    return no_store(Response(TaskSerializer(task).data))


@api_view(["POST"])
@permission_classes([CanUseWorkspace])
def task_restore(request, task_id):
    task = Task.objects.filter(pk=task_id, owner=request.user).first()
    if task is None:
        return error("任务不存在。", 404, code="not_found")
    if task.deleted_at is None:
        return no_store(Response(TaskSerializer(task).data))
    Task.objects.filter(pk=task.pk, version=task.version).update(
        deleted_at=None, version=task.version + 1, updated_at=django_timezone.now()
    )
    task.refresh_from_db()
    return no_store(Response(TaskSerializer(task).data))


@api_view(["POST"])
@permission_classes([CanUseWorkspace])
def task_reorder(request):
    payload = request.data if isinstance(request.data, dict) else {}
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return error("items 必须是非空的顺序数组。", 400, code="invalid_payload")

    ordered_ids = []
    versions: dict = {}
    for item in items:
        if not isinstance(item, dict):
            return error("items 中的元素格式无效。", 400, code="invalid_payload")
        raw_id = str(item.get("id") or "")
        if not raw_id:
            return error("items 中的元素缺少 id。", 400, code="invalid_payload")
        if raw_id in versions:
            return error("items 中存在重复的任务。", 400, code="invalid_payload")
        ordered_ids.append(raw_id)
        try:
            versions[raw_id] = int(item.get("version"))
        except (TypeError, ValueError):
            return error("items 中的元素缺少有效的 version。", 400, code="invalid_payload")

    with transaction.atomic():
        listed = list(Task.objects.filter(id__in=ordered_ids, owner=request.user))
        found = {str(task.id) for task in listed}
        missing = [item for item in ordered_ids if item not in found]
        if missing:
            return error("部分任务不存在或不属于当前账号。", 404, code="not_found")
        for task in listed:
            if task.version != versions[str(task.id)]:
                return error(
                    "任务已被其他设备修改，请刷新后重试。",
                    409,
                    code="version_conflict",
                    current_version=task.version,
                )
        remaining = list(
            Task.objects.filter(owner=request.user, deleted_at__isnull=True)
            .exclude(id__in=ordered_ids)
            .order_by("position", "created_at")
        )
        by_id = {str(task.id): task for task in listed}
        final = [by_id[item] for item in ordered_ids] + remaining
        now = django_timezone.now()
        for index, task in enumerate(final):
            if task.position != index:
                Task.objects.filter(pk=task.pk).update(position=index, updated_at=now)
            if str(task.id) in versions:
                Task.objects.filter(pk=task.pk).update(
                    version=task.version + 1, updated_at=now
                )
    updated = list(Task.objects.filter(id__in=ordered_ids, owner=request.user))
    updated.sort(key=lambda task: task.position)
    return no_store(Response({"results": TaskSerializer(updated, many=True).data}))


# --------------------------------------------------------------------------- #
# projects
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseWorkspace])
def project_list(request):
    if request.method == "GET":
        queryset = visible_queryset(request, Project).annotate(
            task_count=Count("tasks", filter=Q(tasks__deleted_at__isnull=True))
        ).order_by("position", "created_at")
        return no_store(Response(paginate(queryset, request, ProjectSerializer)))

    serializer = ProjectWriteSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data
    highest = Project.objects.filter(owner=request.user).aggregate(value=Max("position"))
    position = (highest["value"] or 0) + 1
    project = Project.objects.create(
        owner=request.user,
        name=data["name"],
        description=data.get("description") or "",
        status=data.get("status") or "active",
        color=data.get("color") or "",
        position=position,
    )
    return Response(ProjectSerializer(project).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseWorkspace])
def project_detail(request, project_id):
    project = Project.objects.filter(pk=project_id, owner=request.user).first()
    if project is None:
        return error("项目不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(ProjectSerializer(project).data))

    if request.method == "DELETE":
        if project.deleted_at is None:
            Project.objects.filter(pk=project.pk).update(
                deleted_at=django_timezone.now(),
                version=project.version + 1,
                updated_at=django_timezone.now(),
            )
            project.refresh_from_db()
        return no_store(Response(ProjectSerializer(project).data))

    serializer = ProjectPatchSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data
    version = data.get("version")
    if version is None:
        return error("更新项目必须提交 version。", 400, code="version_required")

    fields: dict = {}
    if "name" in data:
        fields["name"] = data["name"]
    if "description" in data:
        fields["description"] = data.get("description") or ""
    if "status" in data:
        fields["status"] = data["status"]
    if "color" in data:
        fields["color"] = data.get("color") or ""

    updated = Project.objects.filter(
        pk=project.pk, owner=request.user, version=version, deleted_at__isnull=True
    ).update(version=version + 1, updated_at=django_timezone.now(), **fields)
    if not updated:
        current = Project.objects.filter(pk=project.pk, owner=request.user).first()
        return error(
            "项目已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=current.version if current else None,
        )
    project.refresh_from_db()
    return no_store(Response(ProjectSerializer(project).data))


@api_view(["POST"])
@permission_classes([CanUseWorkspace])
def project_restore(request, project_id):
    project = Project.objects.filter(pk=project_id, owner=request.user).first()
    if project is None:
        return error("项目不存在。", 404, code="not_found")
    if project.deleted_at is None:
        return no_store(Response(ProjectSerializer(project).data))
    Project.objects.filter(pk=project.pk, version=project.version).update(
        deleted_at=None, version=project.version + 1, updated_at=django_timezone.now()
    )
    project.refresh_from_db()
    return no_store(Response(ProjectSerializer(project).data))


# --------------------------------------------------------------------------- #
# tags
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseWorkspace])
def tag_list(request):
    if request.method == "GET":
        queryset = visible_queryset(request, Tag)
        return no_store(Response(paginate(queryset, request, TagSerializer)))

    serializer = TagWriteSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data
    normalized = normalize_tag_name(data["name"])
    if not normalized:
        return error("标签名称不能为空。", 400, code="invalid_payload")
    existing = Tag.objects.filter(owner=request.user, normalized_name=normalized).first()
    if existing is not None:
        return no_store(Response(TagSerializer(existing).data))
    tag = Tag.objects.create(
        owner=request.user,
        name=data["name"].strip(),
        normalized_name=normalized,
        color=data.get("color") or "",
    )
    return Response(TagSerializer(tag).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseWorkspace])
def tag_detail(request, tag_id):
    tag = Tag.objects.filter(pk=tag_id, owner=request.user).first()
    if tag is None:
        return error("标签不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(TagSerializer(tag).data))

    if request.method == "DELETE":
        if tag.deleted_at is None:
            tag.tasks.clear()
            Tag.objects.filter(pk=tag.pk).update(
                deleted_at=django_timezone.now(),
                version=tag.version + 1,
                updated_at=django_timezone.now(),
            )
            tag.refresh_from_db()
        return no_store(Response(TagSerializer(tag).data))

    serializer = TagPatchSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data
    version = data.get("version")
    if version is None:
        return error("更新标签必须提交 version。", 400, code="version_required")

    fields: dict = {}
    if "name" in data:
        normalized = normalize_tag_name(data["name"])
        if not normalized:
            return error("标签名称不能为空。", 400, code="invalid_payload")
        fields["name"] = data["name"].strip()
        fields["normalized_name"] = normalized
    if "color" in data:
        fields["color"] = data.get("color") or ""

    updated = Tag.objects.filter(
        pk=tag.pk, owner=request.user, version=version, deleted_at__isnull=True
    ).update(version=version + 1, updated_at=django_timezone.now(), **fields)
    if not updated:
        current = Tag.objects.filter(pk=tag.pk, owner=request.user).first()
        return error(
            "标签已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=current.version if current else None,
        )
    tag.refresh_from_db()
    return no_store(Response(TagSerializer(tag).data))


# --------------------------------------------------------------------------- #
# journal
# --------------------------------------------------------------------------- #
@api_view(["GET", "PUT"])
@permission_classes([CanUseWorkspace])
def journal(request, day):
    try:
        target = date_cls.fromisoformat(str(day))
    except (TypeError, ValueError):
        return error("日期必须是 YYYY-MM-DD 格式。", 400, code="invalid_date")

    entry = DailyEntry.objects.filter(owner=request.user, date=target).first()
    if request.method == "GET":
        if entry is None:
            return no_store(
                Response(
                    {
                        "date": target.isoformat(),
                        "content": "",
                        "version": 0,
                        "exists": False,
                    }
                )
            )
        payload = DailyEntrySerializer(entry).data
        payload["exists"] = True
        return no_store(Response(payload))

    serializer = DailyEntryWriteSerializer(data=request.data if isinstance(request.data, dict) else {})
    if not serializer.is_valid():
        return serializer_error(serializer)
    data = serializer.validated_data
    content = data.get("content") or ""
    version = data.get("version")

    if entry is None:
        try:
            with transaction.atomic():
                created = DailyEntry.objects.create(
                    owner=request.user, date=target, content=content
                )
        except IntegrityError:
            return error("当日记录已被创建，请刷新后重试。", 409, code="version_conflict")
        payload = DailyEntrySerializer(created).data
        payload["exists"] = True
        return Response(payload, status=201)

    if version is None:
        return error("更新每日记录必须提交 version。", 400, code="version_required")
    if version != entry.version:
        return error(
            "每日记录已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=entry.version,
            current=DailyEntrySerializer(entry).data,
        )

    updated = DailyEntry.objects.filter(
        pk=entry.pk, owner=request.user, version=entry.version
    ).update(
        content=content,
        version=entry.version + 1,
        updated_at=django_timezone.now(),
    )
    if not updated:
        current = DailyEntry.objects.filter(pk=entry.pk, owner=request.user).first()
        return error(
            "每日记录已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=current.version if current else None,
        )
    entry.refresh_from_db()
    payload = DailyEntrySerializer(entry).data
    payload["exists"] = True
    return no_store(Response(payload))
