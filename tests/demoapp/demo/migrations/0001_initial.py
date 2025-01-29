# Generated by Django 5.1.1 on 2025-01-07 11:15

import concurrency.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AlternativeJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "version",
                    concurrency.fields.AutoIncVersionField(default=0, help_text="record revision number"),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "curr_async_result_id",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Current (active) AsyncResult is",
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "last_async_result_id",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Latest executed AsyncResult is",
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "datetime_created",
                    models.DateTimeField(auto_now_add=True, help_text="Creation date and time"),
                ),
                (
                    "datetime_queued",
                    models.DateTimeField(
                        blank=True,
                        help_text="Queueing date and time",
                        null=True,
                        verbose_name="Queued At",
                    ),
                ),
                (
                    "repeatable",
                    models.BooleanField(
                        blank=True,
                        default=False,
                        help_text="Indicate if the job can be repeated as-is",
                    ),
                ),
                (
                    "celery_history",
                    models.JSONField(blank=True, default=dict, editable=False),
                ),
                (
                    "local_status",
                    models.CharField(
                        blank=True,
                        default="",
                        editable=False,
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "group_key",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Tasks with the same group key will not run in parallel",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "permissions": (("test_alternativejob", "Can test AlternativeJob"),),
                "abstract": False,
                "default_permissions": (
                    "add",
                    "change",
                    "delete",
                    "view",
                    "queue",
                    "terminate",
                    "inspect",
                    "revoke",
                ),
            },
        ),
        migrations.CreateModel(
            name="Job",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "version",
                    concurrency.fields.AutoIncVersionField(default=0, help_text="record revision number"),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "curr_async_result_id",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Current (active) AsyncResult is",
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "last_async_result_id",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Latest executed AsyncResult is",
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "datetime_created",
                    models.DateTimeField(auto_now_add=True, help_text="Creation date and time"),
                ),
                (
                    "datetime_queued",
                    models.DateTimeField(
                        blank=True,
                        help_text="Queueing date and time",
                        null=True,
                        verbose_name="Queued At",
                    ),
                ),
                (
                    "repeatable",
                    models.BooleanField(
                        blank=True,
                        default=False,
                        help_text="Indicate if the job can be repeated as-is",
                    ),
                ),
                (
                    "celery_history",
                    models.JSONField(blank=True, default=dict, editable=False),
                ),
                (
                    "local_status",
                    models.CharField(
                        blank=True,
                        default="",
                        editable=False,
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "group_key",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Tasks with the same group key will not run in parallel",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("number", models.IntegerField(default=0)),
                (
                    "op",
                    models.CharField(
                        choices=[
                            ("sleep", "sleep"),
                            ("upper", "upper"),
                            ("raise", "raise"),
                            ("progress", "progress"),
                        ],
                        default="upper",
                        help_text="field to control the implementation of the task",
                        max_length=100,
                    ),
                ),
                ("value", models.IntegerField(default=0)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Job",
                "abstract": False,
                "default_permissions": (
                    "add",
                    "change",
                    "delete",
                    "view",
                    "queue",
                    "terminate",
                    "inspect",
                    "revoke",
                ),
            },
        ),
        migrations.CreateModel(
            name="MultipleJob",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "version",
                    concurrency.fields.AutoIncVersionField(default=0, help_text="record revision number"),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "curr_async_result_id",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Current (active) AsyncResult is",
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "last_async_result_id",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Latest executed AsyncResult is",
                        max_length=36,
                        null=True,
                    ),
                ),
                (
                    "datetime_created",
                    models.DateTimeField(auto_now_add=True, help_text="Creation date and time"),
                ),
                (
                    "datetime_queued",
                    models.DateTimeField(
                        blank=True,
                        help_text="Queueing date and time",
                        null=True,
                        verbose_name="Queued At",
                    ),
                ),
                (
                    "repeatable",
                    models.BooleanField(
                        blank=True,
                        default=False,
                        help_text="Indicate if the job can be repeated as-is",
                    ),
                ),
                (
                    "celery_history",
                    models.JSONField(blank=True, default=dict, editable=False),
                ),
                (
                    "local_status",
                    models.CharField(
                        blank=True,
                        default="",
                        editable=False,
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "group_key",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Tasks with the same group key will not run in parallel",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("STANDARD_TASK", "Standard Task"),
                            ("JOB_TASK", "Job Task"),
                        ],
                        max_length=50,
                    ),
                ),
                ("config", models.JSONField(blank=True, default=dict)),
                ("action", models.CharField(blank=True, max_length=500, null=True)),
                ("sentry_id", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "permissions": (("test_multiplejob", "Can test MultipleJob"),),
                "abstract": False,
            },
        ),
    ]
