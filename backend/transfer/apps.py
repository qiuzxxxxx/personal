from django.apps import AppConfig


class TransferConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transfer"
    verbose_name = "文件中转站"