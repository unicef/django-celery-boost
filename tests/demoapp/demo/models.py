from django.db import models

from django_celery_boost.models import AsyncJobModel, CeleryTaskModel


class Job(CeleryTaskModel, models.Model):
    name = models.CharField(max_length=100)
    number = models.IntegerField(default=0)

    class Meta(CeleryTaskModel.Meta):
        verbose_name = "Job"

    op = models.CharField(
        max_length=100,
        choices=(
            ("sleep", "sleep"),
            ("upper", "upper"),
            ("raise", "raise"),
            ("progress", "progress"),
        ),
        default="upper",
        help_text="field to control the implementation of the task",
    )
    value = models.IntegerField(default=0)

    celery_task_name = "demo.tasks.process_job"


class AlternativeJob(CeleryTaskModel, models.Model):
    class Meta(CeleryTaskModel.Meta):
        permissions = (("test_alternativejob", "Can test AlternativeJob"),)

    celery_task_name = "demo.tasks.process_job"


class MultipleJob(AsyncJobModel):
    class Meta(AsyncJobModel.Meta):
        permissions = (("test_multiplejob", "Can test MultipleJob"),)

    celery_task_name = "demo.tasks.process_job"
