from rest_framework.permissions import BasePermission

from accounts.permissions import is_super_admin


def is_transfer_admin(user) -> bool:
    """The transfer station is managed by the highest tier only (qzx / zx)."""
    return is_super_admin(user)


# Historical alias kept for readability at call sites.
is_qzx = is_transfer_admin


class IsTransferAdmin(BasePermission):
    message = "仅最高管理员 qzx / zx 可执行此操作。"

    def has_permission(self, request, view) -> bool:
        return is_transfer_admin(request.user)


class IsQzxOrPublicObject(BasePermission):
    """Object-level gate used by downloads; views perform visibility checks."""

    message = "该文件为私密投递，仅上传者与最高管理员可访问。"

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(
            getattr(obj, "is_public", False) or is_transfer_admin(request.user)
        )