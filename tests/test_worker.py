import pytest
# from celery.app.base import Celery
# from pytest_celery.api.setup import CeleryTestSetup
# from pytest_celery.vendors.redis.backend.api import RedisTestBackend
# from pytest_celery.vendors.redis.broker.api import RedisTestBroker
# from celery.contrib.pytest import celery_session_worker
from demo.factories import JobFactory
from demo.models import Job

pytestmark = pytest.mark.django_db

# @pytest.fixture
# def default_worker_app(default_worker_app: Celery) -> Celery:
#     app = default_worker_app
#     app.conf.worker_prefetch_multiplier = 1
#     app.conf.worker_concurrency = 1
#     return app
#
#
# @pytest.fixture
# def default_worker_tasks(default_worker_tasks: set) -> set:
#     from demo import tasks
#
#     default_worker_tasks.add(tasks)
#     return default_worker_tasks
#
#
# def test_hello_world(celery_setup: CeleryTestSetup):
#     from demo.tasks import process_job
#     assert isinstance(celery_setup.broker, RedisTestBroker)
#     assert isinstance(celery_setup.backend, RedisTestBackend)
#     assert process_job.s().apply_async().get() is None

@pytest.fixture(scope='session')
def celery_config():
    return {
        'broker_url': 'redis://localhost:6379/0',
        'result_backend': 'redis://localhost:6379/0',
    }
@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {"without_heartbeat": False}

@pytest.mark.celery(result_backend='redis://')
def test_celery_task_info_processed(db, settings, celery_session_worker):
    # settings.CELERY_TASK_ALWAYS_EAGER = True
    job1: Job = JobFactory()
    job1.queue()
    assert job1.async_result.get(timeout=10) == 2
    assert job1.task_info == {}
