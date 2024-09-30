from django.db import models

from django_celery_boost.models import CeleryTaskModel


class Job(CeleryTaskModel, models.Model):
    name = models.CharField(max_length=100)
    number = models.IntegerField(default=0)

    op = models.CharField(
        max_length=100,
        choices=(
            ("sleep", "sleep"),
            ("upper", "upper"),
            ("raise", "raise"),
        ),
        default="upper",
        help_text="field to control the implementation of the task",
    )
    value = models.IntegerField(default=0)

    celery_task_name = "demo.tasks.process_job"
