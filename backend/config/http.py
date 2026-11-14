"""Small request/response helpers shared by the workspace APIs."""
from __future__ import annotations

from datetime import date, datetime

from django.core.paginator import EmptyPage, Paginator
from django.utils import timezone
from rest_framework.response import Response

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


class BadRequest(ValueError):
    """Raised for a field that cannot be parsed."""


def parse_date(value: str, field: str = "date") -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise BadRequest(f"{field} 必须是 YYYY-MM-DD 格式。") from None


def parse_datetime(value: str, field: str = "datetime") -> datetime:
    """Parse an ISO datetime; naive values are interpreted as Asia/Shanghai."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise BadRequest(f"{field} 必须是 ISO-8601 时间。") from None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


def parse_int(value, field: str, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{field} 必须是整数。") from None
    if minimum is not None and parsed < minimum:
        raise BadRequest(f"{field} 不能小于 {minimum}。")
    if maximum is not None and parsed > maximum:
        raise BadRequest(f"{field} 不能大于 {maximum}。")
    return parsed


def no_store(response: Response) -> Response:
    response["Cache-Control"] = "private, no-store"
    return response


def error(detail: str, status: int, code: str | None = None, **extra) -> Response:
    payload = {"detail": detail}
    if code:
        payload["code"] = code
    payload.update(extra)
    return Response(payload, status=status)


def page_size(request) -> int:
    raw = request.query_params.get("page_size")
    if raw in (None, ""):
        return DEFAULT_PAGE_SIZE
    return parse_int(raw, "page_size", 1, MAX_PAGE_SIZE)


def paginate(queryset, request, serializer_class):
    paginator = Paginator(queryset, page_size(request))
    raw = request.query_params.get("page")
    number = 1 if raw in (None, "") else parse_int(raw, "page", 1)
    try:
        page = paginator.page(number)
    except EmptyPage:
        return {
            "results": [],
            "page": number,
            "page_size": paginator.per_page,
            "count": paginator.count,
            "pages": paginator.num_pages,
        }
    return {
        "results": serializer_class(page.object_list, many=True).data,
        "page": number,
        "page_size": paginator.per_page,
        "count": paginator.count,
        "pages": paginator.num_pages,
    }
