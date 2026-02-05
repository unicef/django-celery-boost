from unittest import mock

import pytest
from demo.factories import user_grant_permission
from demo.models import Job
from django.urls import reverse

pytestmark = [pytest.mark.admin]


@pytest.fixture
def job():
    from demo.factories import JobFactory

    return JobFactory()


@pytest.fixture
def queued():
    from demo.factories import JobFactory

    queued = JobFactory()
    queued.queue()
    return queued


def test_celery_changelist(django_app, std_user, job):
    url = reverse("admin:demo_job_changelist")

    with user_grant_permission(std_user, ["demo.view_job"]):
        assert std_user.has_perm("demo.view_job")
        res = django_app.get(url, user=std_user)
    assert res.status_code == 200


def test_celery_change(django_app, std_user, job):
    url = reverse("admin:demo_job_change", args=(job.id,))
    with user_grant_permission(std_user, ["demo.change_job"]):
        res = django_app.get(url, user=std_user)
    assert res.status_code == 200


def test_celery_inspect(django_app, std_user, job):
    url = reverse("admin:demo_job_celery_inspect", args=[job.pk])
    job.queue()
    res = django_app.get(url, user=std_user, expect_errors=True)
    assert res.status_code == 403

    with user_grant_permission(std_user, ["demo.inspect_job"]):
        res = django_app.get(url, user=std_user)
        assert res.status_code == 200


def test_celery_queue(request, django_app, std_user, job):
    url = reverse("admin:demo_job_celery_queue", args=[job.pk])
    res = django_app.get(url, user=std_user, expect_errors=True)
    assert res.status_code == 403

    with user_grant_permission(std_user, ["demo.queue_job", "demo.change_job"]):
        res = django_app.get(url, user=std_user)
        assert res.status_code == 200

        res = res.forms[1].submit().follow()
        msgs = res.context["messages"]
        assert [m.message for m in msgs] == ["Queued"]

        res = django_app.get(url, user=std_user).follow()
        msgs = res.context["messages"]
        assert [m.message for m in msgs] == ["Task has already been queued."]


def test_celery_terminate(request, django_app, std_user, job):
    url = reverse("admin:demo_job_celery_terminate", args=[job.pk])
    res = django_app.get(url, user=std_user, expect_errors=True)
    assert res.status_code == 403

    with user_grant_permission(std_user, ["demo.terminate_job", "demo.change_job"]):
        res = django_app.get(url, user=std_user).follow()
        msgs = res.context["messages"]
        assert [m.message for m in msgs] == ["Task not queued."]
        with mock.patch.object(Job, "is_queued", lambda s: True):
            res = django_app.get(url, user=std_user)
            res = res.forms[1].submit().follow()
            msgs = res.context["messages"]
            assert [m.message for m in msgs] == ["UNKNOWN"]


def test_celery_revoke(request, django_app, std_user, job):
    url = reverse("admin:demo_job_celery_revoke", args=[job.pk])
    res = django_app.get(url, user=std_user, expect_errors=True)
    assert res.status_code == 403

    with mock.patch.object(job, "is_queued", lambda: True):
        with user_grant_permission(std_user, ["demo.revoke_job", "demo.change_job"]):
            res = django_app.get(url, user=std_user).follow()
            msgs = res.context["messages"]
            assert [m.message for m in msgs] == ["Task not queued."]

            with mock.patch.object(Job, "is_queued") as m:
                m.return_value = True
                res = django_app.get(url, user=std_user)
                res = res.forms[1].submit().follow()
                msgs = res.context["messages"]
                assert [m.message for m in msgs] == ["Revoked"]


def test_check_status(request, django_app, std_user, job, queued):
    url = reverse("admin:demo_job_check_status")
    res = django_app.get(url, user=std_user)
    assert res.status_code == 302


def test_celery_cancel_permission(django_app, std_user, job):
    """Test cancel requires terminate permission."""
    url = reverse("admin:demo_job_celery_cancel", args=[job.pk])
    res = django_app.get(url, user=std_user, expect_errors=True)
    assert res.status_code == 403


def test_celery_cancel_not_started(django_app, std_user, job):
    """Test cancel only works for STARTED tasks."""
    url = reverse("admin:demo_job_celery_cancel", args=[job.pk])

    with user_grant_permission(std_user, ["demo.terminate_job", "demo.change_job"]):
        res = django_app.get(url, user=std_user).follow()
        msgs = res.context["messages"]
        assert [m.message for m in msgs] == ["Cancel is only available for running (STARTED) tasks."]

        job.queue()
        res = django_app.get(url, user=std_user).follow()
        msgs = res.context["messages"]
        assert [m.message for m in msgs] == ["Cancel is only available for running (STARTED) tasks."]


def test_celery_cancel_started(django_app, std_user, job):
    """Test cancel works for STARTED tasks."""
    url = reverse("admin:demo_job_celery_cancel", args=[job.pk])
    job.queue()

    with user_grant_permission(std_user, ["demo.terminate_job", "demo.change_job"]):
        with mock.patch.object(Job, "task_status", Job.STARTED):
            res = django_app.get(url, user=std_user)
            assert res.status_code == 200

            res = res.forms[1].submit().follow()
            msgs = res.context["messages"]
            assert [m.message for m in msgs] == ["Graceful termination requested."]

            job.refresh_from_db()
            assert job.is_termination_requested is True


def test_celery_cancel_failure(django_app, std_user, job):
    """Test cancel shows error when request_cancellation fails."""
    url = reverse("admin:demo_job_celery_cancel", args=[job.pk])
    job.queue()

    with user_grant_permission(std_user, ["demo.terminate_job", "demo.change_job"]):
        with mock.patch.object(Job, "task_status", Job.STARTED):
            with mock.patch.object(Job, "request_cancellation", return_value=False):
                res = django_app.get(url, user=std_user)
                res = res.forms[1].submit().follow()
                msgs = res.context["messages"]
                assert [m.message for m in msgs] == ["Could not request graceful termination."]


def test_progress_info(db):
    """Test progress_info admin method."""
    from demo.factories import JobFactory
    from django_celery_boost.admin import CeleryTaskModelAdmin

    admin = CeleryTaskModelAdmin(Job, None)
    job = JobFactory()

    assert admin.progress_info(job) == "Unknown"

    job.queue()
    job.set_total(100)
    job.set_progress(75)
    assert admin.progress_info(job) == "75/100"
