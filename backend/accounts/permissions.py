from rest_framework.permissions import BasePermission

# Highest tier: full control, including the transfer station.
SUPER_ADMIN_USERNAMES = {"qzx"}
# Admin tier: account management over lower-ranked accounts only.
ADMIN_USERNAMES = SUPER_ADMIN_USERNAMES | {"sqx"}


def is_account_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False) and user.username in ADMIN_USERNAMES
    )


def is_super_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and user.username in SUPER_ADMIN_USERNAMES
    )


def account_rank(user) -> int:
    """2 = super admin (qzx), 1 = admin (sqx), 0 = regular account."""
    if not getattr(user, "is_authenticated", False):
        return 0
    if user.username in SUPER_ADMIN_USERNAMES:
        return 2
    if user.username in ADMIN_USERNAMES:
        return 1
    return 0


class IsAccountAdmin(BasePermission):
    message = "仅管理员 qzx / sqx 可执行此操作。"

    def has_permission(self, request, view) -> bool:
        return is_account_admin(request.user)