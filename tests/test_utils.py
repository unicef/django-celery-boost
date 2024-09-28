from unittest import mock

from demo.factories import JobFactory
from demo.models import Job


def test_model_checks(db):
    assert Job.check() == []
    with mock.patch("demo.models.Job.celery_task_name", "==="):
        errors = Job.check()
        assert errors
        assert errors[0].msg == "'demo.job': Cannot import Celery task '==='"

    with mock.patch("demo.models.Job.celery_task_name", "demo.models.Job"):
        errors = Job.check()
        assert errors
        assert errors[0].msg == "'demo.job' is using a non registered Celery task. (demo.models.Job)"

    with mock.patch("demo.models.Job.celery_task_name", ""):
        errors = Job.check()
        assert errors
        assert errors[0].msg == "'demo.job' does not have a Celery task name."


def test_discard_all(db):
    job: Job = JobFactory()
    job.queue()

    Job.discard_all()


def test_purge(db):
    Job.purge()


#
# def test_celery_stats(db):
#     Job.celery_stats()
