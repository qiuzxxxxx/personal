from django.db import migrations, models

import uuid

import chat.models


class Migration(migrations.Migration):
    dependencies = [("chat", "0005_remove_chatmessage_burn_fields")]

    operations = [
        migrations.CreateModel(
            name="BBSPost",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="bbs_posts",
                        to="auth.user",
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                ("content", models.TextField(default="", blank=True)),
                (
                    "visibility",
                    models.CharField(
                        choices=[("public", "公开"), ("private", "指定可见")],
                        db_index=True,
                        default="public",
                        max_length=16,
                    ),
                ),
                (
                    "file",
                    models.FileField(upload_to=chat.models.bbs_file_path, blank=True, null=True),
                ),
                ("file_name", models.CharField(default="", max_length=255, blank=True)),
                ("file_size", models.BigIntegerField(default=0)),
                ("file_type", models.CharField(default="", max_length=100, blank=True)),
                ("reply_count", models.PositiveIntegerField(default=0)),
                ("last_reply_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BBSReply",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="replies",
                        to="chat.bbspost",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="bbs_replies",
                        to="auth.user",
                    ),
                ),
                ("content", models.TextField(default="", blank=True)),
                (
                    "file",
                    models.FileField(upload_to=chat.models.bbs_file_path, blank=True, null=True),
                ),
                ("file_name", models.CharField(default="", max_length=255, blank=True)),
                ("file_size", models.BigIntegerField(default=0)),
                ("file_type", models.CharField(default="", max_length=100, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddField(
            model_name="bbspost",
            name="visible_to",
            field=models.ManyToManyField(
                blank=True, related_name="bbs_posts_shared", to="auth.user"
            ),
        ),
    ]