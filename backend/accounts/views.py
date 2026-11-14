from hashlib import sha256
from time import time

from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .logging import client_ip, record
from .models import ActivityLog
from .permissions import (
    ADMIN_USERNAMES,
    IsAccountAdmin,
    account_rank,
    is_account_admin,
    is_super_admin,
)

PRESET_ROLES = {
    "qzx": "最高管理员",
    "sqx": "管理员",
    "yk": "游客（可上传与浏览，无删除权）",
}

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
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.get_full_name() or user.username,
        "role": PRESET_ROLES.get(user.username, "注册用户"),
        "is_qzx": user.username == "qzx",
        "is_admin": user.username in ADMIN_USERNAMES,
        "is_super": is_super_admin(user),
        "is_chat_user": user.username in {"qzx", "sqx"},
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

        record(request, "login", user=user)
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": serialize_user(user),
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
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "已退出登录。"})


class AccountSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.CharField()
    is_admin = serializers.BooleanField()
    is_super = serializers.BooleanField()
    is_chat_user = serializers.BooleanField()
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
                    "is_admin": info["is_admin"],
                    "is_super": info["is_super"],
                    "is_chat_user": info["is_chat_user"],
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
                queryset = queryset.exclude(user__username__in=ADMIN_USERNAMES - {request.user.username})
        else:
            queryset = queryset.filter(user=request.user)

        if is_account_admin(request.user) and not is_super_admin(request.user):
            protected = ADMIN_USERNAMES - {request.user.username}
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
