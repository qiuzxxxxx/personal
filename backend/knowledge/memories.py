"""Personal memory management.

A memory is only ever active after the user confirmed it. Candidates
(``suggested``) stay separate and are never injected into a model request.
Forget removes the body, keeps a body-free audit record and raises the owner
context epoch so that older injected messages stop being used.
Permanent deletion removes both the memory and its revision history.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import MemoryRevision, OwnerContextState, PersonalMemory


class MemoryError(ValueError):
    def __init__(self, detail: str, code: str = "invalid_payload"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


def bump_epoch(owner, *, withdraw: bool = False) -> int:
    """Invalidate cached context for the owner.

    ``withdraw=True`` marks the event as a withdrawal (forget, disable or a
    withdrawn source): the owner gets a new context floor so that already
    injected messages are no longer part of later model requests.
    """
    state, _ = OwnerContextState.objects.get_or_create(owner=owner)
    new_epoch = state.epoch + 1
    new_floor = state.floor_epoch + 1 if withdraw else state.floor_epoch
    OwnerContextState.objects.filter(pk=state.pk).update(
        epoch=new_epoch, floor_epoch=new_floor, updated_at=timezone.now()
    )
    state.refresh_from_db()
    return state.epoch


def current_epoch(owner) -> int:
    state = OwnerContextState.objects.filter(owner=owner).first()
    return state.epoch if state else 1


def current_floor_epoch(owner) -> int:
    """The oldest context epoch that may still be sent to the model."""
    state = OwnerContextState.objects.filter(owner=owner).first()
    return state.floor_epoch if state else 1


def active_memories(owner, project=None) -> list[PersonalMemory]:
    """Confirmed memories that may be used as background for this owner."""
    queryset = PersonalMemory.objects.filter(
        owner=owner, status="active", deleted_at__isnull=True
    ).select_related("project")
    now = timezone.now()
    queryset = queryset.filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now)
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
    if project is None:
        return list(queryset.filter(scope_type="global"))
    return list(queryset.filter(Q(scope_type="global") | Q(project=project)))


def record_revision(memory: PersonalMemory, action: str, actor: str = "") -> None:
    MemoryRevision.objects.create(
        memory=memory,
        owner=memory.owner,
        action=action,
        version=memory.version,
        body_snapshot="" if action == "forget" else memory.content,
        actor=actor[:64],
    )


@transaction.atomic
def create_memory(
    owner,
    *,
    key: str,
    content: str,
    kind: str = "preference",
    scope_type: str = "global",
    project=None,
    evidence_type: str = "user_explicit",
    source_ref: str = "",
    status: str = "active",
    seed_key: str = "",
    actor: str = "",
) -> PersonalMemory:
    if not key:
        raise MemoryError("记忆条目需要 key。")
    if not content:
        raise MemoryError("记忆内容不能为空。")
    if kind not in {"fact", "preference", "goal"}:
        raise MemoryError("记忆类型无效。")
    if scope_type not in {"global", "project"}:
        raise MemoryError("记忆范围无效。")
    if scope_type == "project" and project is None:
        raise MemoryError("项目范围的记忆必须选择项目。")
    if scope_type == "global" and project is not None:
        project = None

    existing = PersonalMemory.objects.filter(
        owner=owner, key=key, scope_type=scope_type, status="active"
    ).first()
    if existing is not None:
        raise MemoryError(
            "同一范围下已存在同 key 的启用记忆，请编辑原条目。", code="duplicate_key"
        )

    memory = PersonalMemory(
        owner=owner,
        key=key[:128],
        content=content,
        kind=kind,
        scope_type=scope_type,
        project=project,
        status=status,
        evidence_type=evidence_type,
        source_ref=source_ref[:255],
        seed_key=seed_key[:64],
    )
    if status == "active":
        memory.confirmed_at = timezone.now()
    memory.save()
    record_revision(memory, "create" if status == "active" else "suggest", actor)
    bump_epoch(owner)
    return memory


@transaction.atomic
def update_memory(memory: PersonalMemory, *, expected_version: int, changes: dict, actor: str = ""):
    if memory.version != expected_version:
        raise MemoryError("记忆已被其他设备修改，请刷新后重试。", code="version_conflict")
    content = changes.get("content")
    if content is not None:
        if not str(content).strip():
            raise MemoryError("记忆内容不能为空。")
        memory.content = str(content)
    if changes.get("kind"):
        memory.kind = changes["kind"]
    if changes.get("scope_type"):
        memory.scope_type = changes["scope_type"]
    if "project" in changes:
        memory.project = changes["project"]
    if changes.get("evidence_type"):
        memory.evidence_type = changes["evidence_type"]
    memory.version += 1
    memory.save()
    record_revision(memory, "update", actor)
    bump_epoch(memory.owner)
    return memory


@transaction.atomic
def accept_memory(memory: PersonalMemory, *, expected_version: int, actor: str = ""):
    if memory.version != expected_version:
        raise MemoryError("记忆已被其他设备修改，请刷新后重试。", code="version_conflict")
    if memory.status == "active":
        return memory
    memory.status = "active"
    memory.confirmed_at = timezone.now()
    memory.version += 1
    memory.save()
    record_revision(memory, "accept", actor)
    bump_epoch(memory.owner)
    return memory


@transaction.atomic
def disable_memory(memory: PersonalMemory, *, expected_version: int, actor: str = ""):
    if memory.version != expected_version:
        raise MemoryError("记忆已被其他设备修改，请刷新后重试。", code="version_conflict")
    if memory.status in {"forgotten", "superseded"}:
        return memory
    memory.status = "disabled"
    memory.version += 1
    memory.save()
    record_revision(memory, "disable", actor)
    bump_epoch(memory.owner, withdraw=True)
    return memory


@transaction.atomic
def forget_memory(memory: PersonalMemory, *, expected_version: int, actor: str = ""):
    """Remove the body and stop any future use of this memory."""
    if memory.version != expected_version:
        raise MemoryError("记忆已被其他设备修改，请刷新后重试。", code="version_conflict")
    memory.content = ""
    memory.status = "forgotten"
    memory.version += 1
    memory.save()
    record_revision(memory, "forget", actor)
    bump_epoch(memory.owner, withdraw=True)
    return memory


@transaction.atomic
def delete_memory(memory: PersonalMemory, *, expected_version: int) -> None:
    """Permanently remove a memory and its cascading revision history."""
    if memory.version != expected_version:
        raise MemoryError("记忆已被其他设备修改，请刷新后重试。", code="version_conflict")
    owner = memory.owner
    memory.delete()
    # Invalidate both cached and previously injected context. No revision is
    # written here: permanent deletion must leave no memory history record.
    bump_epoch(owner, withdraw=True)


def export_memories(owner) -> list[dict]:
    queryset = PersonalMemory.objects.filter(
        owner=owner, deleted_at__isnull=True
    ).exclude(status="forgotten")
    return [
        {
            "key": item.key,
            "content": item.content,
            "kind": item.kind,
            "scope_type": item.scope_type,
            "project": str(item.project_id or ""),
            "status": item.status,
            "evidence_type": item.evidence_type,
            "source_ref": item.source_ref,
            "confirmed_at": item.confirmed_at.isoformat() if item.confirmed_at else None,
            "updated_at": item.updated_at.isoformat(),
        }
        for item in queryset
    ]
