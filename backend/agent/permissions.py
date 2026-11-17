"""Access control for the AI agent: login required, guest excluded."""
from rest_framework.permissions import BasePermission

from accounts.models import AccountProfile
from accounts.permissions import account_access_level


def can_use_agent(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)) and account_access_level(user) != AccountProfile.GUEST


class CanUseAgent(BasePermission):
    message = "AI 对话需要登录，访客账号没有使用权限。"

    def has_permission(self, request, view) -> bool:
        return can_use_agent(request.user)
