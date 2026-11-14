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
    DailyEntry,
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

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "scheduled_date",
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
    due_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    project = serializers.UUIDField(required=False, allow_null=True, default=None)
    tags = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    client_request_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )


class TaskPatchSerializer(TaskWriteSerializer):
    """Partial update payload. ``version`` is required for conflict detection."""

    title = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True, required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    priority = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False)
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
    name = serializers.CharField(
        max_length=120, allow_blank=False, trim_whitespace=True, required=False
    )
    status = serializers.ChoiceField(choices=PROJECT_STATUS_CHOICES, required=False)
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
