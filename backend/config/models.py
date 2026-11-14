"""Shared abstract models for the personal workspace modules."""
import uuid

from django.db import models
from django.utils import timezone


class VersionedModel(models.Model):
    """UUID primary key, optimistic-concurrency version and soft deletion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = timezone.now()

    def restore(self) -> None:
        self.deleted_at = None
