"""Tests for task tracking and graceful termination functionality."""

from uuid import uuid4

from demo.factories import JobFactory
from demo.models import Job

from django_celery_boost.models import CELERY_BOOST_TRACKING_KEY_PREFIX


def test_tracking_no_task_id(db):
    """Tracking methods should handle missing curr_async_result_id gracefully."""
    job: Job = JobFactory()

    job.set_tracking_info("progress", "50")
    assert job.get_tracking_info() is None
    assert job.tracking_info is None
    assert job.progress == "Unknown"
    job.clear_tracking_info()


def test_tracking_set_get(db):
    """Test setting and getting tracking data."""
    job: Job = JobFactory()
    job.queue()

    job.set_tracking_info("custom_field", "custom_value")
    tracking = job.get_tracking_info()

    assert tracking is not None
    assert tracking["custom_field"] == "custom_value"


def test_set_progress_and_total(db):
    """Test set_progress and set_total helper methods."""
    job: Job = JobFactory()
    job.queue()

    job.set_total(1000)
    job.set_progress(500)

    tracking = job.get_tracking_info()
    assert tracking["total"] == "1000"
    assert tracking["progress"] == "500"


def test_tracking_info_property(db):
    """Test tracking_info property returns same as get_tracking_info."""
    job: Job = JobFactory()
    job.queue()

    job.set_tracking_info("test", "value")
    assert job.tracking_info == job.get_tracking_info()


def test_progress_property(db):
    """Test progress property."""
    job: Job = JobFactory()
    job.queue()

    assert job.progress == "Unknown"

    job.set_total(100)
    job.set_progress(50)
    assert job.progress == "50/100"


def test_tracking_clear(db):
    """Test clearing tracking data."""
    job: Job = JobFactory()
    job.queue()

    job.set_tracking_info("test", "value")
    assert job.get_tracking_info() is not None

    job.clear_tracking_info()
    assert job.get_tracking_info() is None


def test_tracking_key_format(db):
    """Test the Redis key format is correct."""
    job: Job = JobFactory()
    task_id = str(uuid4())
    job.curr_async_result_id = task_id
    job.save()

    expected_key = f"{CELERY_BOOST_TRACKING_KEY_PREFIX}:{task_id}"
    assert job._get_tracking_key() == expected_key


def test_request_cancellation_no_task_id(db):
    """Request cancellation should return False without task ID."""
    job: Job = JobFactory()

    assert job.request_cancellation() is False
    assert job.is_termination_requested is False


def test_request_cancellation(db):
    """Test requesting cancellation."""
    job: Job = JobFactory()
    job.queue()

    assert job.is_termination_requested is False

    result = job.request_cancellation()
    assert result is True
    assert job.is_termination_requested is True

    tracking = job.get_tracking_info()
    assert tracking["terminate_requested"] == "1"


def test_termination_flag_persists_with_tracking(db):
    """Termination flag should persist alongside tracking updates."""
    job: Job = JobFactory()
    job.queue()

    job.request_cancellation()
    assert job.is_termination_requested is True

    job.set_progress(100)
    assert job.is_termination_requested is True


def test_cancel(db):
    """Test cancel method sets status and clears tracking."""
    from unittest.mock import patch, PropertyMock

    job: Job = JobFactory()
    job.queue()

    job.set_total(100)
    job.set_progress(50)
    assert job.get_tracking_info() is not None

    with patch.object(Job, "task_status", new_callable=PropertyMock) as mock_status:
        mock_status.return_value = Job.STARTED
        job.cancel()

    job.refresh_from_db()
    assert job.local_status == Job.CANCELED
    assert job.get_tracking_info() is None


def test_cancel_only_for_started(db):
    """Test cancel only works for STARTED tasks."""
    job: Job = JobFactory()
    job.queue()

    job.set_progress(50)
    job.cancel()

    job.refresh_from_db()
    assert job.local_status != Job.CANCELED
    assert job.get_tracking_info() is not None


def test_get_current_outside_task(db):
    """Test get_current returns None when not in a Celery task."""
    result = Job.get_current()
    assert result is None


def test_get_current_with_mock(db):
    """Test get_current returns the job when in a Celery task context."""
    from unittest.mock import patch, MagicMock

    job: Job = JobFactory()
    job.queue()

    mock_task = MagicMock()
    mock_task.request.id = job.curr_async_result_id

    with patch("celery.current_task", mock_task):
        result = Job.get_current()
        assert result == job
