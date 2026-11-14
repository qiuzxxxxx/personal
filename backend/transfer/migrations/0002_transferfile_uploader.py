from django.conf import settings
from django.db import migrations, models
from django.db.models.deletion import SET_NULL


def restore_reserved_owners(apps, schema_editor):
    TransferFile = apps.get_model("transfer", "TransferFile")
    User = apps.get_model(settings.AUTH_USER_MODEL)
    database = schema_editor.connection.alias
    # These exact labels could only be assigned to logged-in users by the
    # previous upload endpoint. Other legacy labels could be anonymous.
    for user in User.objects.using(database).filter(username__in=["qzx", "sqx", "yk"]):
        TransferFile.objects.using(database).filter(uploader_name=user.username).update(
            uploader_id=user.pk
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("transfer", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="transferfile",
            name="uploader",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL
            ),
        ),
        migrations.RunPython(restore_reserved_owners, migrations.RunPython.noop),
    ]
