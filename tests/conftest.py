import os
import sys
from pathlib import Path

import pytest

here = Path(__file__).parent
sys.path.insert(0, str(here / "../src"))
sys.path.insert(0, str(here / "demoapp"))


def pytest_configure(config):
    os.environ.update(DJANGO_SETTINGS_MODULE="demo.settings")

    import django
    django.setup()
    from django.conf import settings
    settings.CELERY_TASK_ALWAYS_EAGER = False


@pytest.fixture(autouse=True)
def reset_queue():
    from demo.celery import app

    app.control.purge()
