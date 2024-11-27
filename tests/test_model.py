import json
from time import sleep
from unittest import mock
from unittest.mock import Mock, PropertyMock
from uuid import uuid4

from celery.result import AsyncResult
from demo.factories import JobFactory
from demo.models import Job


def test_model_initialize_new(db):
    job: Job = Job()

    assert job.version == 0
    assert job.task_status == Job.NOT_SCHEDULED
    assert job.curr_async_result_id is None
    assert job.async_result is None
    assert not job.is_queued()
    assert job.get_queue_size() == 0
    assert job.get_queue_entries() == []
    assert job.queue_position == 0
    assert job.celery_queue_info() == {
        "canceled": 0,
        "pending": 0,
        "revoked": 0,
        "size": 0,
    }


def test_model_queue(db):
    # from celery import current_app

    job1: Job = JobFactory()
    job2: Job = JobFactory()

    ver = job1.version
    job1.queue()
    sleep(1)
    assert job1.async_result
    # Note the difference in the 2 lines below
    assert job1.async_result.state == Job.PENDING
    assert job1.task_status == Job.QUEUED

    assert job1.async_result.app == Job.celery_app
    assert job1.async_result.id == job1.curr_async_result_id
    assert job1.is_queued()
    assert job1.version == ver

    assert job1.queue_position == 1
    assert job1.get_queue_size() == 1
    redis_entry = json.loads(job1.get_queue_entries()[0])
    assert redis_entry["headers"]["id"] == job1.curr_async_result_id

    assert not job2.is_queued()


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
    assert job1.queue_position == 1

    job2: Job = JobFactory()
    job2.queue()
    assert job2.queue_position == 2


def test_model_queue_info(db):
    job1: Job = JobFactory()
    assert job1.queue_entry == {"id": "NotFound"}
    job1.queue()
    info = job1.queue_entry
    assert info["body"][0] == [job1.pk, job1.version]
    assert info["headers"]["argsrepr"] == f"({job1.pk}, {job1.version})"
    assert info["headers"]["id"] == job1.curr_async_result_id

    job2: Job = JobFactory()
    assert job2.queue_entry == {"id": "NotFound"}

    job3: Job = JobFactory(curr_async_result_id=uuid4())
    assert job3.queue_entry == {"id": "NotFound"}


def test_model_queue_info_redis_reset(db):
    job1: Job = JobFactory()
    assert job1.queue_entry == {"id": "NotFound"}
    job1.queue()
    assert job1.task_status == Job.QUEUED

    # reset celery queue. Simulate Redis crash/flush
    Job.celery_app.control.purge()
    assert job1.queue_entry == {"id": "NotFound"}
    assert job1.task_status == Job.MISSING


def test_model_task_info(db):
    job1: Job = JobFactory()
    assert job1.version == 1

    assert job1.task_info == {"status": Job.NOT_SCHEDULED, "completed_at": ""}
    assert job1.queue()
    job1.refresh_from_db()
    assert job1.version == 1
    assert job1.task_info == {
        "error": "",
        "completed_at": None,
        "last_update": None,
        "query_result_id": None,
        "result": None,
        "started_at": "-",
        "status": Job.PENDING,
    }
    with mock.patch(
        "demo.models.Job.async_result", Mock(_get_task_meta=lambda: {"result": None, "status": Job.REVOKED})
    ):
        assert job1.task_info == {
            "error": "Query execution cancelled.",
            "last_update": None,
            "query_result_id": None,
            "result": None,
            "started_at": "-",
            "completed_at": None,
            "status": Job.REVOKED,
        }


def test_revoke(db):
    job1: Job = JobFactory()

    job1.revoke()

    job1.queue()
    job1.revoke()
    assert job1.task_status == Job.QUEUED


def test_terminate(db):
    job1: Job = JobFactory()
    assert job1.terminate() == Job.UNKNOWN
    assert job1.task_status == Job.NOT_SCHEDULED

    job1.queue()
    assert job1.terminate() == Job.CANCELED

    assert job1.task_status == Job.NOT_SCHEDULED
    assert not job1.is_queued()

    with mock.patch("demo.models.Job.task_status", new_callable=PropertyMock) as m:
        with mock.patch("demo.models.Job.async_result", AsyncResult(id="1")):
            m.return_value = Job.PROGRESS
            assert job1.terminate() == job1.REVOKED
            assert not job1.is_queued()

    job1.queue()
    with mock.patch("demo.models.Job.task_status", new_callable=PropertyMock) as m:
        m.return_value = Job.QUEUED
        with mock.patch("demo.models.Job.celery_queue_entries", return_value=[]):
            assert job1.terminate() == job1.CANCELED
