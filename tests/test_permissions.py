from demo.factories import JobFactory, user_grant_permission
from django.contrib.auth.models import Permission, User


def test_permissions_created(db):
    job = JobFactory()
    assert Permission.objects.filter(content_type__app_label="demo", codename="queue_job").exists()
    assert Permission.objects.filter(content_type__app_label="demo", codename="test_alternativejob").exists()

    assert Permission.objects.filter(content_type__app_label="demo", codename="queue_alternativejob").exists()
