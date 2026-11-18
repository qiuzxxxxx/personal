"""Serializers for the workspace APIs.

Input is validated through explicit serializers; client payloads are never
written into models directly.
"""
from __future__ import annotations

from pathlib import Path

from rest_framework import serializers

from .models import (
    PROJECT_STATUS,
    TASK_PRIORITY,
    TASK_STATUS,
    CalendarBlock,
    DailyEntry,
    FocusSession,
    Folder,
    Material,
    Project,
    Tag,
    Task,
    TaskMaterial,
)

STATUS_CHOICES = [choice[0] for choice in TASK_STATUS]
PRIORITY_CHOICES = [choice[0] for choice in TASK_PRIORITY]
PROJECT_STATUS_CHOICES = [choice[0] for choice in PROJECT_STATUS]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "normalized_name", "color", "version", "created_at", "updated_at"]


class ProjectSerializer(serializers.ModelSerializer):
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "status",
            "color",
            "position",
            "version",
            "task_count",
            "created_at",
            "updated_at",
        ]

    def get_task_count(self, obj: Project) -> int:
        return getattr(obj, "task_count", 0)


class TaskSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    project_name = serializers.SerializerMethodField()
    project_deleted = serializers.SerializerMethodField()
    is_scheduled = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "scheduled_date",
            "estimated_minutes",
            "is_scheduled",
            "due_at",
            "completed_at",
            "position",
            "version",
            "project",
            "project_name",
            "project_deleted",
            "tags",
            "created_at",
            "updated_at",
        ]

    def get_project_name(self, obj: Task) -> str:
        return obj.project.name if obj.project_id else ""

    def get_project_deleted(self, obj: Task) -> bool:
        return bool(obj.project_id and obj.project.deleted_at)

    def get_is_scheduled(self, obj: Task) -> bool:
        return obj.scheduled_date is not None


class DailyEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyEntry
        fields = ["id", "date", "content", "version", "created_at", "updated_at"]


class FolderSerializer(serializers.ModelSerializer):
    material_count = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = [
            "id",
            "name",
            "position",
            "version",
            "material_count",
            "created_at",
            "updated_at",
        ]

    def get_material_count(self, obj: Folder) -> int:
        return getattr(obj, "material_count", 0)


class MaterialSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    extension = serializers.SerializerMethodField()
    is_previewable = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    folder_name = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = [
            "id",
            "original_name",
            "extension",
            "detected_mime",
            "size_bytes",
            "sha256",
            "remark",
            "source",
            "state",
            "folder",
            "folder_name",
            "tags",
            "version",
            "is_previewable",
            "download_url",
            "preview_url",
            "created_at",
            "updated_at",
        ]

    def get_extension(self, obj: Material) -> str:
        return Path(obj.original_name).suffix.lower().lstrip(".")

    def get_is_previewable(self, obj: Material) -> bool:
        from .library import is_previewable

        return is_previewable(obj.original_name)

    def get_download_url(self, obj: Material) -> str:
        return f"/api/library/materials/{obj.id}/download/"

    def get_preview_url(self, obj: Material) -> str:
        if not self.get_is_previewable(obj):
            return ""
        return f"/api/library/materials/{obj.id}/download/?inline=1"

    def get_folder_name(self, obj: Material) -> str:
        return obj.folder.name if obj.folder_id else ""


class TaskMaterialSerializer(serializers.ModelSerializer):
    material = MaterialSerializer(read_only=True)

    class Meta:
        model = TaskMaterial
        fields = ["id", "task", "material", "created_at"]


class TaskWriteSerializer(serializers.Serializer):
    """Payload for creating or updating a task."""

    title = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(
        max_length=20000, required=False, allow_blank=True, default=""
    )
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False, default="todo")
    priority = serializers.ChoiceField(
        choices=PRIORITY_CHOICES, required=False, default="normal"
    )
    scheduled_date = serializers.DateField(required=False, allow_null=True, default=None)
    estimated_minutes = serializers.IntegerField(
        required=False, min_value=1, max_value=720, default=45
    )
    due_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    project = serializers.UUIDField(required=False, allow_null=True, default=None)
    tags = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    client_request_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )


class TaskPatchSerializer(TaskWriteSerializer):
    """Partial update payload. ``version`` is required for conflict detection.

    Every optional field is redeclared without a default: a field that keeps
    the create-time default would always appear in ``validated_data`` and the
    view would treat it as "provided", silently clearing description, dates,
    project and tags on every PATCH.
    """

    title = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True, required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False)
    description = serializers.CharField(max_length=20000, required=False, allow_blank=True)
    scheduled_date = serializers.DateField(required=False, allow_null=True)
    estimated_minutes = serializers.IntegerField(
        required=False, min_value=1, max_value=720
    )
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    project = serializers.UUIDField(required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.UUIDField(), required=False)
    client_request_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    version = serializers.IntegerField(required=False, min_value=1)


class ProjectWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(
        max_length=10000, required=False, allow_blank=True, default=""
    )
    status = serializers.ChoiceField(
        choices=PROJECT_STATUS_CHOICES, required=False, default="active"
    )
    color = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


class ProjectPatchSerializer(ProjectWriteSerializer):
    """Partial update payload; optional fields must not carry defaults.

    See ``TaskPatchSerializer`` for why the defaults have to be dropped.
    """

    name = serializers.CharField(
        max_length=120, allow_blank=False, trim_whitespace=True, required=False
    )
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=PROJECT_STATUS_CHOICES, required=False)
    color = serializers.CharField(max_length=32, required=False, allow_blank=True)
    version = serializers.IntegerField(required=False, min_value=1)


class TagWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, allow_blank=False, trim_whitespace=True)
    color = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


class TagPatchSerializer(TagWriteSerializer):
    name = serializers.CharField(
        max_length=64, allow_blank=False, trim_whitespace=True, required=False
    )
    version = serializers.IntegerField(required=False, min_value=1)


class DailyEntryWriteSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=50000, required=False, allow_blank=True, default=""
    )
    version = serializers.IntegerField(required=False, min_value=1)


class CalendarBlockSerializer(serializers.ModelSerializer):
    task_id = serializers.SerializerMethodField()
    start_time = serializers.TimeField(format="%H:%M")
    end_time = serializers.TimeField(format="%H:%M")

    class Meta:
        model = CalendarBlock
        fields = [
            "id",
            "task_id",
            "title",
            "block_type",
            "day_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "is_completed",
            "version",
            "created_at",
            "updated_at",
        ]

    def get_task_id(self, obj: CalendarBlock) -> str | None:
        return str(obj.task_id) if obj.task_id else None


class CalendarBlockWriteSerializer(serializers.Serializer):
    task_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )
    block_type = serializers.ChoiceField(
        choices=[choice[0] for choice in CalendarBlock.BLOCK_TYPES],
        required=False,
        default="task",
    )
    day_date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField(required=False, allow_null=True)
    duration_minutes = serializers.IntegerField(
        required=False, min_value=5, max_value=720
    )
    is_completed = serializers.BooleanField(required=False, default=False)


class CalendarBlockPatchSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=False)
    block_type = serializers.ChoiceField(
        choices=[choice[0] for choice in CalendarBlock.BLOCK_TYPES], required=False
    )
    day_date = serializers.DateField(required=False)
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)
    duration_minutes = serializers.IntegerField(
        required=False, min_value=5, max_value=720
    )
    is_completed = serializers.BooleanField(required=False)
    version = serializers.IntegerField(required=False, min_value=1)


class FocusSessionSerializer(serializers.ModelSerializer):
    task_id = serializers.SerializerMethodField()

    class Meta:
        model = FocusSession
        fields = ["id", "task_id", "target_title", "minutes", "created_at"]

    def get_task_id(self, obj: FocusSession) -> str | None:
        return str(obj.task_id) if obj.task_id else None


class FocusSessionWriteSerializer(serializers.Serializer):
    task_id = serializers.UUIDField(required=False, allow_null=True)
    target_title = serializers.CharField(
        max_length=200, allow_blank=False, trim_whitespace=True
    )
    minutes = serializers.IntegerField(min_value=1, max_value=480)
