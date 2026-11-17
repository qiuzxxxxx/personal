from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from accounts.models import AccountProfile
from accounts.permissions import ADMIN_USERNAMES, is_account_admin
from .models import AgentAttachment, Conversation, Message


AI_RETENTION_HOURS = 24

def _permanent_user_ids():
    return User.objects.filter(
        Q(username__in=ADMIN_USERNAMES)
        | Q(account_profile__access_level=AccountProfile.ADMIN)
    ).values_list("id", flat=True)


def _attachment_ids(messages) -> set[str]:
    result: set[str] = set()
    for message in messages:
        for item in message.attachments or []:
            if isinstance(item, dict) and item.get("id"):
                result.add(str(item["id"]))
    return result


def purge_expired_agent_history(user=None) -> dict[str, int]:
    if user is not None and is_account_admin(user):
        return {"messages": 0, "conversations": 0, "attachments": 0}

    cutoff = timezone.now() - timedelta(hours=AI_RETENTION_HOURS)
    owner_filter = (
        Q(conversation__user=user)
        if user is not None
        else ~Q(conversation__user_id__in=_permanent_user_ids())
    )
    expired = list(
        Message.objects.filter(owner_filter, created_at__lt=cutoff).only(
            "id", "attachments"
        )
    )
    expired_ids = [item.id for item in expired]
    if expired_ids:
        Message.objects.filter(id__in=expired_ids).delete()

    conversations = Conversation.objects.exclude(user_id__in=_permanent_user_ids())
    if user is not None:
        conversations = conversations.filter(user=user)
    empty = conversations.filter(messages__isnull=True, updated_at__lt=cutoff)
    conversation_count = empty.count()
    empty.delete()

    remaining = Message.objects.exclude(
        conversation__user_id__in=_permanent_user_ids()
    )
    if user is not None:
        remaining = remaining.filter(conversation__user=user)
    live_attachment_ids = _attachment_ids(remaining.only("attachments"))

    attachments = AgentAttachment.objects.exclude(user_id__in=_permanent_user_ids()).filter(
        created_at__lt=cutoff
    )
    if user is not None:
        attachments = attachments.filter(user=user)
    stale = [item for item in attachments if str(item.id) not in live_attachment_ids]
    for attachment in stale:
        attachment.file.delete(save=False)
    if stale:
        AgentAttachment.objects.filter(id__in=[item.id for item in stale]).delete()

    return {
        "messages": len(expired_ids),
        "conversations": conversation_count,
        "attachments": len(stale),
    }
