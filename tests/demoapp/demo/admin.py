from demo.models import Job
from django.contrib import admin

from celery_model.admin import CeleryTaskModelAdmin


@admin.register(Job)
class JobAdmin(CeleryTaskModelAdmin, admin.ModelAdmin):
    pass
