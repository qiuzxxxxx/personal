"""Lightweight liveness and readiness checks.

Section 12.6 asks for a cheap probe that reports the process state and the
state of the database and Redis without exposing any user data.
"""
from __future__ import annotations

from django.db import connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


def _check_database() -> tuple[bool, str]:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - the probe reports the failure
        return False, type(exc).__name__
    return True, "ok"


def _check_redis() -> tuple[bool, str]:
    from django.core.cache import cache

    try:
        cache.set("zixxx:health", "1", timeout=10)
        if cache.get("zixxx:health") == "1":
            return True, "ok"
    except Exception as exc:  # noqa: BLE001 - the probe reports the failure
        return False, type(exc).__name__
    return False, "unavailable"


@never_cache
def health(request):
    """Readiness probe: the dependencies decide the answer."""
    database_ok, database_detail = _check_database()
    redis_ok, redis_detail = _check_redis()
    ready = database_ok and redis_ok
    return JsonResponse(
        {
            "status": "ok" if ready else "degraded",
            "database": {"ok": database_ok, "detail": database_detail},
            "redis": {"ok": redis_ok, "detail": redis_detail},
        },
        status=200 if ready else 503,
    )


@never_cache
def live(request):
    """Liveness probe: the process itself is enough."""
    return JsonResponse({"status": "ok"})
