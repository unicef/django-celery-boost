from demo.models import Job
from django.contrib import admin

from django_celery_boost.admin import CeleryTaskModelAdmin


@admin.register(Job)
class JobAdmin(CeleryTaskModelAdmin, admin.ModelAdmin):
    list_display = ("__str__", "queue_position", "task_status")
