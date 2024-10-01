import pytest
from demo.factories import JobFactory
from demo.models import Job

pytestmark = [pytest.mark.django_db, pytest.mark.eager]


def test_celery_task_info_processed(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    job1: Job = JobFactory()
    assert job1.queue() == job1.curr_async_result_id
    assert job1.task_status == Job.MISSING
