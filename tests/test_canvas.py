from typing import cast

from celery import chain, group, chord
from celery.worker import WorkController

from demo.factories import AddToJobFactory, SumJobFactory, ValueJobFactory
from demo.models import AddToJob, SumJob, ValueJob

pytest_plugins = ("celery.contrib.pytest",)


def test_chain(transactional_db: None, celery_worker: WorkController) -> None:
    value_job = cast(ValueJob, ValueJobFactory(value=5))
    add_to_job = cast(AddToJob, AddToJobFactory(value=15))
    assert chain(value_job.s(), add_to_job.s())().get() == value_job.value + add_to_job.value


def test_group(transactional_db: None, celery_worker: WorkController) -> None:
    value_jobs = [cast(ValueJob, ValueJobFactory(value=i)) for i in range(1, 4)]
    assert group([job.s() for job in value_jobs])().get() == [1, 2, 3]


def test_chord(transactional_db: None, celery_worker: WorkController) -> None:
    value_jobs = [cast(ValueJob, ValueJobFactory(value=i)) for i in range(1, 4)]
    sum_job = cast(SumJob, SumJobFactory())
    assert chord([job.s() for job in value_jobs])(sum_job.s()).get() == 6
