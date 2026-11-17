from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transfer", "0003_transferfile_visible_until_transferannouncement"),
    ]

    operations = [
        migrations.AddField(
            model_name="transferannouncement",
            name="login_content",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="transferannouncement",
            name="login_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
