import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def seed_existing_announcements(apps, schema_editor):
    Announcement = apps.get_model("transfer", "TransferAnnouncement")
    History = apps.get_model("transfer", "AnnouncementHistory")
    item = Announcement.objects.order_by("-updated_at").first()
    if item is None:
        return
    if item.content.strip():
        History.objects.create(
            kind="transfer",
            content=item.content,
            published_by_id=item.updated_by_id,
            created_at=item.updated_at,
        )
    if item.login_content.strip():
        History.objects.create(
            kind="login",
            content=item.login_content,
            published_by_id=item.updated_by_id,
            created_at=item.login_updated_at or item.updated_at,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("transfer", "0004_transferannouncement_login_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AnnouncementHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("transfer", "中转站公告"),
                            ("login", "登录页公告"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("content", models.TextField()),
                (
                    "created_at",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now
                    ),
                ),
                (
                    "published_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="announcement_history",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "公告历史",
                "verbose_name_plural": "公告历史",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.RunPython(
            seed_existing_announcements, migrations.RunPython.noop
        ),
    ]
