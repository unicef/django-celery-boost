from typing import cast

import pytest

from demo.factories import AddToJobFactory, JobFactory
from demo.models import AddToJob, Job
from django_celery_boost.models import InvalidTaskBase, APP_LABEL, MODEL_NAME

pytestmark = [pytest.mark.django_db]


def test_can_create_signature_using_different_methods() -> None:
    job = cast(AddToJob, AddToJobFactory())
    assert job.signature() == job.s()


def test_signature_parameters() -> None:
    job = cast(AddToJob, AddToJobFactory())
    signature = job.signature()
    assert signature.task == job.celery_task_name
    assert signature.args == (job.id, job.version)
    assert signature.kwargs == {APP_LABEL: AddToJob._meta.app_label, MODEL_NAME: AddToJob._meta.model_name}


def test_cannot_create_signature_without_correct_base_task() -> None:
    with pytest.raises(InvalidTaskBase):
        job = cast(Job, JobFactory())
        job.s()
