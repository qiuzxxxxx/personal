"""Public "about" page content API.

GET  /api/about/          — public, no authentication required.
PUT  /api/about/          — highest administrator (qzx) only.
"""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.logging import record as audit_log
from accounts.models import SiteAbout
from accounts.permissions import is_super_admin

TEXT_LIMITS = {
    "site_name": 100,
    "tagline": 200,
    "intro": 5000,
    "features": 5000,
    "developer": 200,
    "contact": 500,
    "app_version": 100,
    "guide": 5000,
}
LINKS_MAX = 10


def serialize_about(item: SiteAbout) -> dict:
    return {
        "site_name": item.site_name,
        "tagline": item.tagline,
        "intro": item.intro,
        "features": item.features,
        "developer": item.developer,
        "contact": item.contact,
        "app_version": item.app_version,
        "guide": item.guide,
        "links": item.links if isinstance(item.links, list) else [],
        "updated_at": item.updated_at,
    }


def _clean_links(raw) -> tuple[list[dict], str | None]:
    """Normalize the editable link list; return (links, error)."""
    if raw in (None, ""):
        return [], None
    if not isinstance(raw, list):
        return [], "链接列表格式不正确。"
    links: list[dict] = []
    for entry in raw[:LINKS_MAX]:
        if not isinstance(entry, dict):
            return [], "链接条目格式不正确。"
        label = str(entry.get("label") or "").strip()[:100]
        url = str(entry.get("url") or "").strip()[:500]
        if not label or not url:
            continue
        if not url.startswith(("http://", "https://", "/")):
            return [], f"链接「{label}」必须以 http(s):// 或 / 开头。"
        links.append({"label": label, "url": url})
    return links, None


@api_view(["GET", "PUT"])
@permission_classes([AllowAny])
def site_about(request: Request):
    item = SiteAbout.load()

    if request.method == "GET":
        return Response(serialize_about(item), headers={"Cache-Control": "no-store"})

    if not is_super_admin(request.user):
        return Response({"detail": "仅最高管理员可以编辑关于页面。"}, status=403)

    errors: dict[str, str] = {}
    updates: dict[str, object] = {}
    for field, limit in TEXT_LIMITS.items():
        value = str(request.data.get(field) or "").strip()
        if len(value) > limit:
            errors[field] = f"不能超过 {limit} 个字符。"
        else:
            updates[field] = value

    links, link_error = _clean_links(request.data.get("links"))
    if link_error:
        errors["links"] = link_error
    else:
        updates["links"] = links

    if errors:
        return Response({"detail": "存在校验错误。", "errors": errors}, status=400)

    for field, value in updates.items():
        setattr(item, field, value)
    item.updated_by = request.user
    item.save()
    audit_log(request, "site_about_update", user=request.user)
    return Response(serialize_about(item))
