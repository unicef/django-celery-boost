from uuid import uuid4

from demo.factories import JobFactory
from demo.models import Job

from django_celery_boost.models import CELERY_BOOST_TRACKING_KEY_PREFIX


def test_tracking_no_task_id(db):
    job: Job = JobFactory()

    job.set_tracking("test")
    assert job.get_tracking() is None
    assert job.tracking is None
    assert job.tracking_message == ""
    job.clear_tracking()


def test_tracking_set_get(db):
    job: Job = JobFactory()
    job.queue()

    job.set_tracking("50% - Processing 500/1000")
    tracking = job.get_tracking()

    assert tracking is not None
    assert tracking["message"] == "50% - Processing 500/1000"


def test_tracking_property(db):
    job: Job = JobFactory()
    job.queue()

    job.set_tracking("Test message")
    assert job.tracking == job.get_tracking()


def test_tracking_message_property(db):
    job: Job = JobFactory()
    job.queue()

    assert job.tracking_message == ""

    job.set_tracking("Processing...")
    assert job.tracking_message == "Processing..."


def test_tracking_clear(db):
    job: Job = JobFactory()
    job.queue()

    job.set_tracking("Test")
    assert job.get_tracking() is not None

    job.clear_tracking()
    assert job.get_tracking() is None


def test_tracking_key_format(db):
    job: Job = JobFactory()
    task_id = str(uuid4())
    job.curr_async_result_id = task_id
    job.save()

    expected_key = f"{CELERY_BOOST_TRACKING_KEY_PREFIX}:{task_id}"
    assert job._get_tracking_key() == expected_key


def test_request_termination_no_task_id(db):
    job: Job = JobFactory()

    assert job.request_graceful_termination() is False
    assert job.is_termination_requested() is False


def test_request_termination(db):
    job: Job = JobFactory()
    job.queue()

    assert job.is_termination_requested() is False

    result = job.request_graceful_termination()
    assert result is True
    assert job.is_termination_requested() is True

    tracking = job.get_tracking()
    assert tracking["terminate_requested"] == "1"
    assert "terminate_requested_at" in tracking


def test_termination_flag_persists_with_tracking(db):
    job: Job = JobFactory()
    job.queue()

    job.request_graceful_termination()
    assert job.is_termination_requested() is True

    job.set_tracking("Still processing...")
    assert job.is_termination_requested() is True
    assert job.tracking_message == "Still processing..."
