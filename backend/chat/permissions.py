from rest_framework.permissions import BasePermission

from .models import CHAT_USERNAMES


def is_chat_user(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and user.username in CHAT_USERNAMES
    )


class IsChatUser(BasePermission):
    message = "该空间仅对 qzx 与 sqx 开放。"

    def has_permission(self, request, view) -> bool:
        return is_chat_user(request.user)