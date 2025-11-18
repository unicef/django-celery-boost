from typing import cast

from celery import chain, group, chord
from celery.worker import WorkController

from _pytest.fixtures import SubRequest
import pytest
from pytest_django.fixtures import SettingsWrapper

from demo.factories import AddToJobFactory, SumJobFactory, ValueJobFactory
from demo.models import AddToJob, SumJob, ValueJob

pytest_plugins = ("celery.contrib.pytest",)


@pytest.fixture(params=[True, False], ids=["eager", "async"])
def execution_mode(request: SubRequest, settings: SettingsWrapper) -> None:
    if request.param:
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_STORE_EAGER_RESULT = True
    else:
        settings.CELERY_TASK_ALWAYS_EAGER = False
        settings.CELERY_TASK_STORE_EAGER_RESULT = False


def test_chain(execution_mode: None, transactional_db: None, celery_worker: WorkController) -> None:
    value_job = cast(ValueJob, ValueJobFactory(value=5))
    add_to_job = cast(AddToJob, AddToJobFactory(value=15))
    assert chain(value_job.s(), add_to_job.s())().get() == value_job.value + add_to_job.value


def test_group(execution_mode: None, transactional_db: None, celery_worker: WorkController) -> None:
    value_jobs = [cast(ValueJob, ValueJobFactory(value=i)) for i in range(1, 4)]
    assert group([job.s() for job in value_jobs])().get() == [1, 2, 3]


def test_chord(execution_mode: None, transactional_db: None, celery_worker: WorkController) -> None:
    value_jobs = [cast(ValueJob, ValueJobFactory(value=i)) for i in range(1, 4)]
    sum_job = cast(SumJob, SumJobFactory())
    assert chord([job.s() for job in value_jobs])(sum_job.s()).get() == 6
