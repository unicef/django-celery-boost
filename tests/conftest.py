import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.hashers import make_password

if TYPE_CHECKING:
    from django.contrib.auth.models import User

here = Path(__file__).parent
DEMOAPP_PATH = here / "demoapp"
sys.path.insert(0, str(here / "../src"))
sys.path.insert(0, str(DEMOAPP_PATH))

CELERY_TASK_DEFAULT_QUEUE = "tests_demo_queue"
CELERY_TASK_REVOKED_QUEUE = "tests_revoked_queue"


def pytest_configure(config):
    os.environ.update(DJANGO_SETTINGS_MODULE="demo.settings")
    os.environ.update(CELERY_TASK_ALWAYS_EAGER="False")

    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_TASK_DEFAULT_QUEUE", CELERY_TASK_DEFAULT_QUEUE)
    os.environ.setdefault("CELERY_TASK_REVOKED_QUEUE", CELERY_TASK_REVOKED_QUEUE)

    import django

    django.setup()
    from django.conf import settings

    settings.AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.CELERY_TASK_STORE_EAGER_RESULT = True
    settings.CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
    settings.DEMOAPP_PATH = DEMOAPP_PATH
    settings.MESSAGE_STORAGE = "demo.messages.PlainCookieStorage"

    from celery.fixups.django import DjangoWorkerFixup

    DjangoWorkerFixup.install = lambda x: None


@pytest.fixture(autouse=True)
def reset_queue():
    # from demo.celery import app
    from demo.models import Job

    Job.purge()
    with Job.celery_app.pool.acquire(block=True) as conn:
        conn.default_channel.client.delete(CELERY_TASK_DEFAULT_QUEUE)
        conn.default_channel.client.delete(CELERY_TASK_REVOKED_QUEUE)


@pytest.fixture()
def std_user(db) -> "User":
    from demo.factories import UserFactory

    return UserFactory(
        username="admin@example.com",
        is_staff=True,
        is_active=True,
        is_superuser=False,
        password=make_password("password"),
    )
