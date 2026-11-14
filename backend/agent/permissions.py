"""Access control for the AI agent: login required, guest excluded."""
from rest_framework.permissions import BasePermission

GUEST_USERNAMES = {"yk", "guest"}


def can_use_agent(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)) and user.username not in GUEST_USERNAMES


class CanUseAgent(BasePermission):
    message = "AI 对话需要登录，游客账号（yk）没有使用权限。"

    def has_permission(self, request, view) -> bool:
        return can_use_agent(request.user)
