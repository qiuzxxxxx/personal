"""Audit logging helper. Recording must never break a request."""
from __future__ import annotations

from ipaddress import ip_address

from django.conf import settings
from django.contrib.auth.models import User


def client_ip(request) -> str | None:
    candidates = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
    candidates.append(request.META.get("REMOTE_ADDR", ""))
    hops = settings.NEXUS_TRUSTED_PROXY_HOPS
    index = len(candidates) - 1 - hops
    forwarded = [candidates[index]] if index >= 0 and hops else []
    for candidate in [*forwarded, candidates[-1]]:
        try:
            return str(ip_address(candidate.strip()))
        except ValueError:
            continue
    return None


def record(request, action: str, user: User | None = None, actor=None, detail: str = "") -> None:
    from .models import ActivityLog

    target = user if getattr(user, "is_authenticated", False) else (user or None)
    if actor is None:
        requester = getattr(request, "user", None)
        actor = requester if getattr(requester, "is_authenticated", False) else None
    try:
        ActivityLog.objects.create(
            user=target,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=str(action)[:48],
            detail=str(detail)[:255],
            ip=client_ip(request),
        )
    except Exception:  # noqa: BLE001 - audit failures must stay silent
        pass
