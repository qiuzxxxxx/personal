from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("chat", "0003_chatmessage_retention")]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="deleted_for_sender",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="deleted_for_recipient",
            field=models.BooleanField(default=False),
        ),
    ]
