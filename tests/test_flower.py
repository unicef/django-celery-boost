from django.test import RequestFactory, override_settings
from django.urls import reverse

import pytest

from django_celery_boost.context_processors import flower as flower_context
from django_celery_boost.utils import (
    CeleryBoostDeprecationWarning,
    get_flower_address,
    resolve_flower_setting,
)


@pytest.fixture
def rf():
    return RequestFactory()


def test_resolve_default():
    with override_settings(CELERY_BOOST_FLOWER=None, CELERY_FLOW_ADDRESS=None):
        assert resolve_flower_setting() == "/flower"


def test_resolve_canonical_wins():
    with override_settings(
        CELERY_BOOST_FLOWER="https://flower.example/flower",
        CELERY_FLOW_ADDRESS="https://legacy.example",
    ):
        assert resolve_flower_setting() == "https://flower.example/flower"


def test_resolve_legacy_alias_is_deprecated():
    with override_settings(CELERY_BOOST_FLOWER=None, CELERY_FLOW_ADDRESS="https://legacy.example/flower"):
        with pytest.warns(CeleryBoostDeprecationWarning):
            assert resolve_flower_setting() == "https://legacy.example/flower"


def test_get_flower_address_autodetect(rf):
    with override_settings(CELERY_BOOST_FLOWER="/flower"):
        assert get_flower_address(rf.get("/admin/")) == "http://testserver/flower"


def test_get_flower_address_relative_without_leading_slash(rf):
    assert get_flower_address(rf.get("/admin/"), "flower") == "http://testserver/flower"


def test_get_flower_address_absolute_passthrough(rf):
    assert get_flower_address(rf.get("/admin/"), "https://flower.example/") == "https://flower.example"


def test_get_flower_address_without_request():
    assert get_flower_address(None, "/flower/") == "/flower"


def test_context_processor(rf):
    with override_settings(CELERY_BOOST_FLOWER="/flower"):
        assert flower_context(rf.get("/admin/")) == {"flower_addr": "http://testserver/flower"}


@pytest.mark.admin
def test_admin_inspect_renders_flower_link(django_app, std_user):
    from demo.factories import JobFactory, user_grant_permission

    job = JobFactory()
    job.queue()
    url = reverse("admin:demo_job_celery_inspect", args=[job.pk])
    with user_grant_permission(std_user, ["demo.inspect_job"]):
        with override_settings(CELERY_BOOST_FLOWER="/flower"):
            res = django_app.get(url, user=std_user)
    assert res.status_code == 200
    assert "/flower/task/" in res.text
