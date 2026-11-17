from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("chat", "0004_chatmessage_visibility")]

    operations = [
        migrations.RemoveField(
            model_name="chatmessage",
            name="burn_after_read_seconds",
        ),
        migrations.RemoveField(
            model_name="chatmessage",
            name="read_at",
        ),
        migrations.RemoveField(
            model_name="chatmessage",
            name="expires_at",
        ),
    ]
