from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def seed_access_levels(apps, schema_editor):
    User = apps.get_model("auth", "User")
    AccountProfile = apps.get_model("accounts", "AccountProfile")
    for user in User.objects.all():
        if user.username in {"qzx", "sqx"}:
            level = "admin"
        elif user.username in {"yk", "guest"}:
            level = "guest"
        else:
            level = "member"
        AccountProfile.objects.update_or_create(
            user_id=user.pk, defaults={"access_level": level}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_accountsecurity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "access_level",
                    models.CharField(
                        choices=[("admin", "管理员"), ("member", "成员"), ("guest", "访客")],
                        db_index=True,
                        default="member",
                        max_length=16,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.RunPython(seed_access_levels, migrations.RunPython.noop),
    ]
