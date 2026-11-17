from rest_framework.permissions import BasePermission

from .models import AccountProfile

# qzx is the only immutable highest administrator. Preset names remain here
# solely as a compatibility fallback before profiles have been migrated.
SUPER_ADMIN_USERNAMES = {"qzx"}
ADMIN_USERNAMES = SUPER_ADMIN_USERNAMES | {"sqx"}


def account_access_level(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return AccountProfile.GUEST
    session = getattr(user, "session", None)
    if session is not None and getattr(session, "owner", None) is not None:
        user = session.owner
    if user.username in SUPER_ADMIN_USERNAMES:
        return AccountProfile.ADMIN
    try:
        return user.account_profile.access_level
    except (AccountProfile.DoesNotExist, AttributeError):
        if user.username == "sqx":
            return AccountProfile.ADMIN
        if user.username in {"yk", "guest"}:
            return AccountProfile.GUEST
        return AccountProfile.MEMBER


def is_account_admin(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)) and account_access_level(user) == AccountProfile.ADMIN


def is_super_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and user.username in SUPER_ADMIN_USERNAMES
    )


def account_rank(user) -> int:
    """2 = qzx, 1 = administrator, 0 = member or guest."""
    if not getattr(user, "is_authenticated", False):
        return 0
    if user.username in SUPER_ADMIN_USERNAMES:
        return 2
    if is_account_admin(user):
        return 1
    return 0


class IsAccountAdmin(BasePermission):
    message = "仅管理员可执行此操作。"

    def has_permission(self, request, view) -> bool:
        return is_account_admin(request.user)


class IsSuperAdmin(BasePermission):
    message = "仅最高管理员 qzx 可执行此操作。"

    def has_permission(self, request, view) -> bool:
        return is_super_admin(request.user)


class CanUseWorkspace(BasePermission):
    message = "访客账号仅可使用文件中转站。"

    def has_permission(self, request, view) -> bool:
        return bool(getattr(request.user, "is_authenticated", False)) and account_access_level(request.user) != AccountProfile.GUEST
