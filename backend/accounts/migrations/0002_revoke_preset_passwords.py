from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import migrations


def revoke_preset_passwords(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Token = apps.get_model("authtoken", "Token")
    database = schema_editor.connection.alias
    legacy_passwords = {"qzx": "11408", "sqx": "224082027", "yk": "123456"}
    usernames = set(legacy_passwords) | {"zx", "guest", "zixuan", "suqianxiang"}
    for user in User.objects.using(database).filter(username__in=usernames):
        candidates = {legacy_passwords.get(user.username, "123456"), "123456"}
        if any(check_password(value, user.password) for value in candidates):
            user.password = make_password(None)
            user.save(using=database, update_fields=["password"])
            Token.objects.using(database).filter(user_id=user.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("authtoken", "0004_alter_tokenproxy_options"),
    ]
    operations = [
        migrations.RunPython(revoke_preset_passwords, migrations.RunPython.noop),
    ]
