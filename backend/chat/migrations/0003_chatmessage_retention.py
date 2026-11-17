from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0002_chatreadstate")]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="burn_after_read_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
