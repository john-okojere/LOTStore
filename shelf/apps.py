from django.apps import AppConfig


class ShelfConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shelf'

    def ready(self):
        from . import signals  # noqa: F401
