from django.db import models

from celery_model.models import CeleryTaskModel


class Job(CeleryTaskModel, models.Model):
    name = models.CharField(max_length=100)
    number = models.IntegerField(default=0)

    celery_task_name = "demo.tasks.process_job"
