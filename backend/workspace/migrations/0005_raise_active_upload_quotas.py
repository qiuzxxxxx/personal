from django.db import migrations


ONE_GIB = 1024 * 1024 * 1024


def raise_active_session_quotas(apps, schema_editor):
    UploadSession = apps.get_model("workspace", "UploadSession")
    UploadSession.objects.filter(state="active").update(
        max_bytes=ONE_GIB,
        max_file_bytes=ONE_GIB,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0004_alter_uploadsession_max_bytes_and_more"),
    ]

    operations = [
        migrations.RunPython(raise_active_session_quotas, migrations.RunPython.noop),
    ]
