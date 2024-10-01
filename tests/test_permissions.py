from django.contrib.auth.models import Permission


def test_permissions_created(db):
    assert Permission.objects.filter(content_type__app_label="demo", codename="queue_job").exists()
    assert Permission.objects.filter(content_type__app_label="demo", codename="test_alternativejob").exists()

    assert Permission.objects.filter(content_type__app_label="demo", codename="queue_alternativejob").exists()
