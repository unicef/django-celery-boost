from unittest import mock

from demo.celery import app
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


def test_model_initialize_new(db):
    job: Job = Job()
    assert job.version == 0
    assert job.status == Job.NOT_SCHEDULED
    assert job.curr_async_result_id is None
    assert job.async_result is None
    assert not job.is_queued()
    assert job.get_celery_queue_position() == 0
    assert job.celery_queue_status() == {
        "canceled": 0,
        "pending": 0,
        "revoked": 0,
        "size": 0,
    }


def test_model_queue(db):
    job: Job = JobFactory()
    ver = job.version
    job.queue()
    assert job.is_queued()
    assert job.async_result
    assert job.async_result.id == job.curr_async_result_id
    assert job.status == Job.QUEUED
    assert job.version == ver


def test_model_disallow_multiple_queue(db):
    job: Job = JobFactory()
    job.queue()
    ar = job.async_result

    arid2 = job.queue()
    assert arid2 is None
    assert job.async_result == ar


def test_model_get_celery_queue_position(db):
    job1: Job = JobFactory()
    job1.queue()
    assert job1.get_celery_queue_position() == 1

    job2: Job = JobFactory()
    job2.queue()
    assert job2.get_celery_queue_position() == 2


def test_model_queue_info(db):
    job1: Job = JobFactory()
    assert job1.queue_info == {"id": "NotFound"}
    job1.queue()
    info = job1.queue_info
    assert info["body"][0] == [job1.id, job1.version]
    assert info["headers"]["argsrepr"] == f"({job1.id}, {job1.version})"
    assert info["headers"]["id"] == job1.curr_async_result_id

    job2: Job = JobFactory()
    assert job2.queue_info == {"id": "NotFound"}


def test_model_queue_info_redis_reset(db):
    job1: Job = JobFactory()
    assert job1.queue_info == {"id": "NotFound"}
    job1.queue()
    assert job1.status == Job.QUEUED

    # reset celery queue. Simulate Redis crash/flush
    app.control.purge()
    assert job1.queue_info == {"id": "NotFound"}
    assert job1.status == Job.MISSING


def test_model_task_info(db):
    job1: Job = JobFactory()
    assert job1.task_info is None
    job1.queue()
    assert job1.task_info == {
        "error": "",
        "last_update": None,
        "query_result_id": None,
        "result": None,
        "started_at": 0,
        "status": Job.PENDING,
    }


def test_terminate(db):
    job1: Job = JobFactory()
    assert job1.terminate() == ""
    assert job1.status == Job.NOT_SCHEDULED

    job1.queue()
    assert job1.terminate() == job1.CANCELED
    assert job1.status == Job.CANCELED


def test_discard_all(db):
    Job.discard_all()


def test_purge(db):
    Job.purge()


def test_celery_queue_status(db):
    job1: Job = JobFactory()
    job2: Job = JobFactory()
    job3: Job = JobFactory()
    job1.queue()
    job2.queue()
    job3.queue()

    job2.terminate()

    assert Job.celery_queue_status() == {
        "canceled": 1,
        "pending": 1,
        "revoked": 1,
        "size": 2,
    }
