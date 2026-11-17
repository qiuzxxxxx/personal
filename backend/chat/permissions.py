from rest_framework.permissions import BasePermission

from accounts.models import AccountProfile
from accounts.permissions import account_access_level, is_super_admin


def is_chat_user(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and account_access_level(user) != AccountProfile.GUEST
    )


class IsChatUser(BasePermission):
    message = "访客账号不能使用聊天功能。"

    def has_permission(self, request, view) -> bool:
        return is_chat_user(request.user)


class CanUseForum(BasePermission):
    """留言板对所有非访客成员开放，无需对方也同时在线或双向绑定。"""

    message = "留言板仅对成员与管理員开放。"

    def has_permission(self, request, view) -> bool:
        return is_chat_user(request.user)


def can_chat_with(sender, recipient) -> bool:
    if not is_chat_user(sender) or not is_chat_user(recipient) or sender.pk == recipient.pk:
        return False
    return is_super_admin(sender) or is_super_admin(recipient)
