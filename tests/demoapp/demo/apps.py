from django.apps import AppConfig


class Config(AppConfig):
    name = "demo"

    def ready(self) -> None:
        from . import celery  # noqa
        from . import tasks  # noqa
