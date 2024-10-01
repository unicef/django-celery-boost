import os
from time import sleep

import pytest
from demo.factories import JobFactory
from demo.models import Job

pytest_plugins = ("celery.contrib.pytest",)

SLEEP_TIME = 0.2


@pytest.fixture(scope="session")
def celery_config():
    return {"broker_url": os.environ["CELERY_BROKER_URL"], "result_backend": os.environ["CELERY_BROKER_URL"]}


@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "shutdown_timeout": 60,
    }


@pytest.fixture()
def celery_app(celery_app):
    from demo.models import Job

    Job._celery_app = celery_app
    Job.purge()
    return celery_app


def test_tasks_success(transactional_db, celery_app, celery_worker):
    job: Job = JobFactory(name="abc", op="upper")
    job.queue()
    sleep(SLEEP_TIME)
    assert job.async_result.result == "ABC"
    assert job.task_status == Job.SUCCESS
    assert job.task_info["date_done"]


def test_tasks_fail(transactional_db, celery_app, celery_worker):
    job1: Job = JobFactory(name="Error #1", op="raise")
    job1.queue()
    sleep(SLEEP_TIME)
    assert isinstance(job1.async_result.result, Exception)
    assert job1.task_status == Job.FAILURE
    assert job1.task_info["traceback"]
    assert job1.task_info["date_done"]
    assert job1.task_info["error"] == job1.name


#
# def test_task_terminate(transactional_db):
#     job1: Job = JobFactory(name="Progress", op="progress", value=5)
#
#     aid = job1.curr_async_result_id
#     job1.queue()
#     job1.terminate()
#     assert list(job1.celery_queue_entries()) == []
#     job1.terminate()
#


def test_tasks_progress(transactional_db, celery_app, celery_worker):
    job1: Job = JobFactory(name="Progress", op="progress", value=5)
    job1.queue()
    sleep(2)
    assert job1.task_status == Job.PROGRESS
    assert job1.task_info["result"]["current"] >= 2 / 0.5
    sleep(3)
    assert job1.task_status == Job.SUCCESS


def test_tasks_terminate_before_start(transactional_db, celery_app, reset_queue):
    job1: Job = JobFactory(name="Terminate Before", op="loop", value=10)
    job1.queue()
    job1.terminate()
    assert job1.task_status == Job.NOT_SCHEDULED


def test_celery_queue_status_no_app(transactional_db, reset_queue):
    Job.purge()
    assert Job.get_queue_size() == 0
    job1: Job = JobFactory()
    job2: Job = JobFactory()
    job3: Job = JobFactory()
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 0, "revoked": 0, "size": 0}

    job1.queue()
    job2.queue()
    job3.queue()
    sleep(1)
    assert Job.get_queue_size() == 3
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 3, "revoked": 0, "size": 3}


def test_celery_queue_status_no_workers(transactional_db, celery_app, reset_queue):
    assert Job.get_queue_size() == 0
    job1: Job = JobFactory()
    job2: Job = JobFactory()
    job3: Job = JobFactory()
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 0, "revoked": 0, "size": 0}

    job1.queue()
    job2.queue()

    job2.terminate()
    job3.terminate()

    sleep(1)
    assert Job.get_queue_size() == 1
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 1, "revoked": 1, "size": 1}

    job11 = JobFactory()
    job11.terminate()
    with Job.celery_app.pool.acquire(block=True) as conn:
        conn.default_channel.client.delete(Job.celery_task_queue)
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 0, "revoked": 1, "size": 0}


def test_celery_queue_status_workers(transactional_db, celery_app, celery_worker, reset_queue):
    assert Job.get_queue_size() == 0
    job1: Job = JobFactory()
    job2: Job = JobFactory()
    job3: Job = JobFactory()
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 0, "revoked": 0, "size": 0}

    job1.queue()
    job2.queue()
    job3.queue()
    sleep(1)
    assert Job.get_queue_size() == 0
    assert Job.celery_queue_info() == {"canceled": 0, "pending": 0, "revoked": 0, "size": 0}


def test_revoke(transactional_db, celery_app, celery_worker, reset_queue):
    job1: Job = JobFactory(name="Terminate Before", op="loop", value=5)

    job1.queue()
    job1.revoke()
    assert job1.task_status == Job.MISSING
