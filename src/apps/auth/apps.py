from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "api"
    name = "apps.auth"
    verbose_name = "Auth"
