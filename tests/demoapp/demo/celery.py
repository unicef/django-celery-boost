import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "demo.settings")
app = Celery("demo-celery-model")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
