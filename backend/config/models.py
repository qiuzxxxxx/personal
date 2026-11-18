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

    def bump_version(self) -> int:
        """Persist an optimistic-lock version increment and refresh this instance.

        Business rules that change several fields in one transaction should
        still use explicit ``update(version=version + 1, ...)`` statements when
        the previous version must be checked atomically. This helper is for
        owner-scoped actions where a stale write cannot cross accounts, such as
        syncing ``Task.scheduled_date`` from a calendar block.
        """

        type(self).objects.filter(pk=self.pk).update(
            version=models.F("version") + 1,
            updated_at=timezone.now(),
        )
        self.refresh_from_db(fields=["version", "updated_at"])
        return self.version
