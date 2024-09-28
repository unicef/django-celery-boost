import pytest
from django.urls import reverse

pytestmark = [pytest.mark.admin]


@pytest.fixture()
def job():
    from demo.factories import JobFactory

    return JobFactory()


@pytest.fixture()
def queued():
    from demo.factories import JobFactory

    queued = JobFactory()
    queued.queue()
    return queued


def test_celery_changelist(django_app, admin_user, job):
    url = reverse("admin:demo_job_changelist")
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 200


def test_celery_change(django_app, admin_user, job):
    url = reverse("admin:demo_job_change", args=(job.id,))
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 200


def test_celery_discard_all(django_app, admin_user):
    url = reverse("admin:demo_job_celery_discard_all")
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 302


def test_celery_purge(django_app, admin_user):
    url = reverse("admin:demo_job_celery_purge")
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 302


def test_celery_terminate(django_app, admin_user, job):
    url = reverse("admin:demo_job_celery_terminate", args=[job.pk])
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 302


def test_celery_inspect(django_app, admin_user, job):
    url = reverse("admin:demo_job_celery_inspect", args=[job.pk])
    job.queue()
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 200


# def test_celery_result(request, django_app, admin_user, job):
#     url = reverse("admin:demo_job_celery_result", args=[job.pk])
#     job.queue()
#     res = django_app.get(url, user=admin_user)
#     assert res.status_code == 302
#


def test_celery_queue(request, django_app, admin_user, job):
    url = reverse("admin:demo_job_celery_queue", args=[job.pk])
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 302
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 302


# def test_celery_run(request, django_app, admin_user, job):
#     url = reverse("admin:demo_job_run", args=[job.pk])
#     res = django_app.get(url, user=admin_user)
#     assert res.status_code == 200
#


def test_check_status(request, django_app, admin_user, job, queued):
    url = reverse("admin:demo_job_check_status")
    res = django_app.get(url, user=admin_user)
    assert res.status_code == 302
