import os
from secrets import token_urlsafe

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rest_framework.authtoken.models import Token

from accounts.models import AccountProfile

PRESET_USERNAMES = ("qzx", "sqx", "yk")


class Command(BaseCommand):
    help = "创建 qzx / sqx / yk 账号，并为未设置密码的账号设置初始密码"

    @transaction.atomic
    def handle(self, *args, **options):
        generated = []
        for username in PRESET_USERNAMES:
            user = User.objects.filter(username=username).first()
            if user and user.has_usable_password():
                continue

            env_name = f"NEXUS_PASSWORD_{username.upper()}"
            password = os.environ.get(env_name)
            if password is not None and not 12 <= len(password) <= 128:
                raise CommandError(f"{env_name} 必须包含 12 至 128 个字符。")
            if not password:
                if getattr(settings, "IS_PRODUCTION", False):
                    # Production must not print generated secrets into the
                    # container logs, so the operator has to provide them.
                    raise CommandError(
                        f"生产环境必须通过环境变量 {env_name} 提供 {username} 的初始密码。"
                    )
                password = token_urlsafe(24)
                generated.append((username, password))
            if user is None:
                user = User(username=username, first_name=username)
            try:
                validate_password(password, user)
            except ValidationError as exc:
                raise CommandError(f"{env_name}：{' '.join(exc.messages)}") from None
            user.set_password(password)
            user.save()
            access_level = (
                AccountProfile.ADMIN
                if username in {"qzx", "sqx"}
                else AccountProfile.GUEST
            )
            AccountProfile.objects.update_or_create(
                user=user, defaults={"access_level": access_level}
            )
            Token.objects.filter(user=user).delete()

        if generated:
            self.stdout.write("以下为本次生成的初始密码，请安全保存：")
            for username, password in generated:
                self.stdout.write(f"{username}: {password}")
        self.stdout.write(self.style.SUCCESS("预置账号初始化完成。"))
