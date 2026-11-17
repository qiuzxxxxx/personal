from hashlib import sha256
from time import time

from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .logging import client_ip, record
from .models import AccountLock, ActivityLog, AccountProfile, AccountSecurity, SiteMaintenance
from .permissions import (
    SUPER_ADMIN_USERNAMES,
    IsAccountAdmin,
    IsSuperAdmin,
    account_access_level,
    account_rank,
    is_account_admin,
    is_super_admin,
)


def invalidate_upload_sessions(user):
    """Logouts and password resets must close phone upload sessions."""
    from workspace.models import UploadSession
    from workspace.upload_views import revoke_session

    AccountSecurity.bump(user)
    for session in UploadSession.objects.filter(owner=user, state="active"):
        revoke_session(session)


MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
LOGIN_WINDOW_SECONDS = 300


def login_allowed(ip: str | None, username: str) -> bool:
    bucket = int(time()) // LOGIN_WINDOW_SECONDS
    for value, limit in ((f"ip:{ip}", 120), (f"account:{ip}:{username.casefold()}", 12)):
        key = f"login:{bucket}:{sha256(value.encode()).hexdigest()}"
        if cache.add(key, 1, timeout=LOGIN_WINDOW_SECONDS):
            continue
        try:
            attempts = cache.incr(key)
        except ValueError:
            continue
        if attempts > limit:
            return False
    return True


def serialize_user(user: User) -> dict:
    access_level = account_access_level(user)
    if is_super_admin(user):
        role = "最高管理员"
    else:
        role = dict(AccountProfile.ACCESS_CHOICES).get(access_level, "成员")
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "role": role,
        "access_level": access_level,
        "is_qzx": user.username == "qzx",
        "is_admin": is_account_admin(user),
        "is_super": is_super_admin(user),
        "is_chat_user": access_level != AccountProfile.GUEST,
        "is_guest": access_level == AccountProfile.GUEST,
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        if not username or not password or len(username) > 150 or len(password) > MAX_PASSWORD_LENGTH:
            return Response({"detail": "请输入用户名和密码。"}, status=400)
        if not login_allowed(client_ip(request), username):
            return Response(
                {"detail": "登录尝试过多，请稍后再试。"},
                status=429,
                headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)},
            )

        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            existing = User.objects.filter(username=username).first()
            record(request, "login_failed", user=existing, detail=f"username={username}")
            return Response({"detail": "用户名或密码不正确。"}, status=401)

        # 维护模式：仅最高管理员可登录
        maintenance = SiteMaintenance.load()
        if maintenance.enabled and not is_super_admin(user):
            record(request, "login_maintenance_blocked", user=user)
            reason = maintenance.reason or "系统维护中，请稍后再试。"
            return Response(
                {"detail": f"系统维护中。{reason}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 账号锁定：仅超级管理员可解锁
        try:
            lock = AccountLock.objects.get(user=user)
            if lock.locked and not is_super_admin(user):
                record(request, "login_account_locked", user=user)
                lock_reason = lock.reason or "该账号已被锁定，请联系管理员。"
                return Response(
                    {"detail": f"账号已锁定。{lock_reason}"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except AccountLock.DoesNotExist:
            pass

        # A login always rotates the token. The newest login remains active and
        # every previous browser/device is rejected on its next request.
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            Token.objects.filter(user=locked_user).delete()
            token = Token.objects.create(user=locked_user)
            locked_user.last_login = timezone.now()
            locked_user.save(update_fields=["last_login"])
        record(request, "login", user=locked_user)
        return Response(
            {
                "token": token.key,
                "user": serialize_user(locked_user),
            },
            headers={"Cache-Control": "no-store"},
        )


class MeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": serialize_user(request.user)})


class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        record(request, "logout", user=request.user)
        Token.objects.filter(key=request.auth.key).delete()
        invalidate_upload_sessions(request.user)
        return Response({"detail": "已退出登录。"})


class AccountSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.CharField()
    access_level = serializers.ChoiceField(choices=AccountProfile.ACCESS_CHOICES)
    is_admin = serializers.BooleanField()
    is_super = serializers.BooleanField()
    is_chat_user = serializers.BooleanField()
    is_guest = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)
    date_joined = serializers.DateTimeField()
    log_count = serializers.IntegerField()


class ActivityLogSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    actor_username = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "username",
            "actor_username",
            "action",
            "detail",
            "ip",
            "created_at",
        ]

    def get_username(self, obj: ActivityLog):
        return obj.user.username if obj.user else None

    def get_actor_username(self, obj: ActivityLog):
        return obj.actor.username if obj.actor else None


class UsersListView(APIView):
    """Admin-only roster of accounts."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAccountAdmin]

    def get(self, request):
        users = User.objects.order_by("id")
        data = []
        for user in users:
            info = serialize_user(user)
            data.append(
                {
                    "username": info["username"],
                    "role": info["role"],
                    "access_level": info["access_level"],
                    "is_admin": info["is_admin"],
                    "is_super": info["is_super"],
                    "is_chat_user": info["is_chat_user"],
                    "is_guest": info["is_guest"],
                    "last_login": user.last_login,
                    "date_joined": user.date_joined,
                    "log_count": ActivityLog.objects.filter(user=user).count(),
                }
            )
        return Response(AccountSerializer(data, many=True).data)


class LogsView(APIView):
    """Own logs for any logged-in user; other accounts' logs for admins only."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        username = str(request.query_params.get("username") or "").strip()
        scope_all = request.query_params.get("scope") == "all"
        try:
            limit = min(max(int(request.query_params.get("limit") or 200), 1), 500)
        except ValueError:
            return Response({"detail": "limit 必须为整数。"}, status=400)

        queryset = ActivityLog.objects.select_related("user", "actor")
        if username:
            if username != request.user.username:
                target = User.objects.filter(username=username).first()
                target_rank = account_rank(target) if target else 0
                allowed = is_super_admin(request.user) or (
                    is_account_admin(request.user) and target_rank == 0
                )
                if not allowed:
                    return Response(
                        {"detail": "该账号的日志仅最高管理员 qzx 可以查看。"},
                        status=403,
                    )
            queryset = queryset.filter(user__username=username)
        elif scope_all and is_account_admin(request.user):
            if not is_super_admin(request.user):
                protected = [
                    user.username
                    for user in User.objects.all()
                    if user.pk != request.user.pk and account_rank(user) > 0
                ]
                queryset = queryset.exclude(user__username__in=protected)
        else:
            queryset = queryset.filter(user=request.user)

        if is_account_admin(request.user) and not is_super_admin(request.user):
            protected = [
                user.username
                for user in User.objects.all()
                if user.pk != request.user.pk and account_rank(user) > 0
            ]
            queryset = queryset.exclude(actor__username__in=protected)
        rows = queryset[:limit]
        response = Response(ActivityLogSerializer(rows, many=True).data)
        response["Cache-Control"] = "no-store"
        return response


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH, trim_whitespace=False
    )


class ChangePasswordView(APIView):
    """Admins (qzx / sqx) may reset another account's password."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAccountAdmin]

    def post(self, request, username):
        target = User.objects.filter(username=username).first()
        if target is None:
            return Response({"detail": "账号不存在。"}, status=404)
        if target.id == request.user.id:
            return Response(
                {"detail": "该接口用于修改其他账号的密码，不能修改自己。"},
                status=400,
            )
        if account_rank(request.user) <= account_rank(target) or target.is_staff or target.is_superuser:
            return Response(
                {"detail": "无权重置同级或更高级管理员的密码。"},
                status=403,
            )

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["new_password"]
        try:
            password_validation.validate_password(password, target)
        except ValidationError as exc:
            raise serializers.ValidationError({"new_password": exc.messages}) from None
        with transaction.atomic():
            target.set_password(password)
            target.save(update_fields=["password"])
            Token.objects.filter(user=target).delete()
        invalidate_upload_sessions(target)
        record(
            request,
            "password_changed",
            user=target,
            actor=request.user,
            detail=f"by {request.user.username}",
        )
        return Response(
            {
                "detail": f"已重置 {target.username} 的密码，其旧登录会话已失效。",
                "user": serialize_user(target),
            }
        )


class CreateAccountSerializer(serializers.Serializer):
    username = serializers.RegexField(
        regex=r"^[\w.@+-]+$", max_length=150,
        error_messages={"invalid": "用户名只能包含字母、数字及 @ . + - _。"},
    )
    password = serializers.CharField(
        min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH, trim_whitespace=False
    )
    access_level = serializers.ChoiceField(choices=AccountProfile.ACCESS_CHOICES)

    def validate_username(self, value: str) -> str:
        username = value.strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("该用户名已存在。")
        return username

    def validate(self, attrs):
        candidate = User(username=attrs["username"], first_name=attrs["username"])
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except ValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from None
        return attrs


class AccountAccessSerializer(serializers.Serializer):
    access_level = serializers.ChoiceField(choices=AccountProfile.ACCESS_CHOICES)


class AccountCreateView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = CreateAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["username"],
                first_name=data["username"],
                password=data["password"],
            )
            AccountProfile.objects.create(user=user, access_level=data["access_level"])
        record(
            request,
            "account_created",
            user=user,
            actor=request.user,
            detail=f"access={data['access_level']}",
        )
        return Response(serialize_user(user), status=201)


class AccountDetailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsSuperAdmin]

    def _target(self, username):
        return User.objects.filter(username=username).first()

    def patch(self, request, username):
        target = self._target(username)
        if target is None:
            return Response({"detail": "账号不存在。"}, status=404)
        if is_super_admin(target):
            return Response({"detail": "最高管理员 qzx 的权限不可修改。"}, status=400)
        serializer = AccountAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_level = serializer.validated_data["access_level"]
        AccountProfile.objects.update_or_create(
            user=target, defaults={"access_level": access_level}
        )
        record(
            request,
            "account_permission_changed",
            user=target,
            actor=request.user,
            detail=f"access={access_level}",
        )
        return Response(serialize_user(target))

    def delete(self, request, username):
        target = self._target(username)
        if target is None:
            return Response({"detail": "账号不存在。"}, status=404)
        if is_super_admin(target) or target.pk == request.user.pk:
            return Response({"detail": "最高管理员 qzx 不能被删除。"}, status=400)
        if target.is_staff or target.is_superuser:
            return Response({"detail": "Django 系统管理员不能在此处删除。"}, status=403)
        target_name = target.username
        record(
            request,
            "account_deleted",
            user=target,
            actor=request.user,
            detail=f"username={target_name}",
        )
        target.delete()
        return Response(status=204)


# ---------------------------------------------------------------------------
# 维护模式 + 账号锁定 API（仅超级管理员）
# ---------------------------------------------------------------------------

class SiteMaintenanceSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    reason = serializers.CharField(max_length=500, allow_blank=True)


class AccountLockSerializer(serializers.Serializer):
    username = serializers.CharField()
    locked = serializers.BooleanField()
    reason = serializers.CharField(max_length=255, allow_blank=True)


class MaintenanceStatusView(APIView):
    """获取全局维护状态。登录页需要在失效 Token 下也能读取。"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        maintenance = SiteMaintenance.load()
        return Response({
            "enabled": maintenance.enabled,
            "reason": maintenance.reason,
        })


class MaintenanceToggleView(APIView):
    """切换维护模式开关。仅最高管理员可操作。"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = SiteMaintenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        maintenance = SiteMaintenance.load()
        maintenance.enabled = serializer.validated_data["enabled"]
        maintenance.reason = serializer.validated_data["reason"]
        maintenance.save(update_fields=["enabled", "reason", "updated_at"])
        if maintenance.enabled:
            # 进入维护后，非最高管理员的既有会话立即失效，避免仅拦截新登录。
            Token.objects.exclude(user__username__in=SUPER_ADMIN_USERNAMES).delete()
        record(request, "maintenance_toggled", detail=f"enabled={maintenance.enabled}")
        return Response({
            "enabled": maintenance.enabled,
            "reason": maintenance.reason,
        })


class AccountLockListView(APIView):
    """列出所有被锁定的账号。仅最高管理员可操作。"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        locks = AccountLock.objects.filter(locked=True).select_related("user").order_by("locked_at")
        data = []
        for lock in locks:
            data.append({
                "username": lock.user.username,
                "reason": lock.reason,
                "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                "locked_by": lock.locked_by.username if lock.locked_by else None,
            })
        return Response(data)


class AccountLockToggleView(APIView):
    """锁定/解锁指定账号。仅最高管理员可操作。"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = AccountLockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"].strip().lower()
        locked = serializer.validated_data["locked"]
        reason = serializer.validated_data["reason"]

        user = User.objects.filter(username__iexact=username, is_active=True).first()
        if user is None:
            return Response({"detail": "账号不存在。"}, status=404)
        if is_super_admin(user):
            return Response(
                {"detail": "不能锁定最高管理员 qzx。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lock, created = AccountLock.objects.get_or_create(user=user)
        lock.locked = locked
        lock.reason = reason
        lock.locked_by = request.user
        if locked:
            lock.locked_at = timezone.now()
        else:
            lock.locked_at = None
        lock.save(update_fields=["locked", "reason", "locked_by", "locked_at", "updated_at"])

        # 锁定：踢出该账号所有已登录会话
        if locked:
            Token.objects.filter(user=user).delete()
            invalidate_upload_sessions(user)

        record(
            request,
            "account_lock_toggled",
            user=user,
            actor=request.user,
            detail=f"locked={locked} by={request.user.username}",
        )
        return Response({
            "username": user.username,
            "locked": lock.locked,
            "reason": lock.reason,
        })

