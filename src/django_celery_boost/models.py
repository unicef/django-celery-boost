import base64
import json
import logging
from typing import TYPE_CHECKING, Any, Callable, Generator

import sentry_sdk
from celery import states
from celery.app.base import Celery
from celery.result import AsyncResult
from concurrency.api import concurrency_disable_increment
from concurrency.fields import AutoIncVersionField
from django.conf import settings
from django.core import checks
from django.db import models
from django.utils import timezone
from django.utils.functional import classproperty
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from django_celery_boost.signals import task_queued, task_revoked, task_terminated

if TYPE_CHECKING:
    import celery.app.control
    from kombu.connection import Connection
    from kombu.transport.redis import Channel

logger = logging.getLogger(__name__)


class CeleryManager:
    pass


class CeleryTaskModel(models.Model):
    STARTED = states.STARTED  # (task has been started)
    SUCCESS = states.SUCCESS  # (task executed successfully)
    PENDING = states.PENDING  # (waiting for execution or unknown task id)
    FAILURE = states.FAILURE  # (task execution resulted in exception)
    RETRY = states.RETRY  # (task is being retried)
    REVOKED = states.REVOKED  # (task has been revoked)
    RECEIVED = states.RECEIVED  # Task was received by a worker (only used in events).
    REJECTED = states.REJECTED  # #: Task was rejected (only used in events).

    DONE = "DONE"  # task hae successfully processed
    PROGRESS = "PROGRESS"  # task is in progress: NOTE: must be handled by the task
    QUEUED = "QUEUED"  # (task exists in Redis but unknown to Celery)
    CANCELED = "CANCELED"  # (task is canceled BEFORE worker fetch it)
    NOT_SCHEDULED = "Not scheduled"
    MISSING = "MISSING"  # Task seems scheduled (it has a ResultID, but is not present in Celery)
    UNKNOWN = "UNKNOWN"  # Task is UNKNOWN

    ACTIVE_STATUSES = frozenset({states.PENDING, states.RECEIVED, states.STARTED, states.RETRY, QUEUED})
    TERMINATED_STATUSES = frozenset({states.REJECTED, states.REVOKED, states.FAILURE})

    version = AutoIncVersionField()
    description = models.CharField(max_length=255, blank=True, null=True)

    curr_async_result_id = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        editable=False,
        help_text="Current (active) AsyncResult is",
    )
    last_async_result_id = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        editable=False,
        help_text="Latest executed AsyncResult is",
    )
    datetime_created = models.DateTimeField(auto_now_add=True, help_text="Creation date and time")
    datetime_queued = models.DateTimeField("Queued At", blank=True, null=True, help_text="Queueing date and time")
    repeatable = models.BooleanField(default=False, blank=True, help_text="Indicate if the job can be repeated as-is")

    celery_history = models.JSONField(default=dict, blank=True, null=False, editable=False)
    local_status = models.CharField(max_length=100, default="", blank=True, null=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="%(app_label)s_%(class)s_jobs",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    group_key = models.CharField(
        max_length=255,
        blank=True,
        editable=False,
        null=True,
        help_text="Tasks with the same group key will not run in parallel",
    )
    default_celery_task_name: str = ""
    "FQN of the task processing this Model's instances"

    celery_task_queue: str = settings.CELERY_TASK_DEFAULT_QUEUE
    """Name of the queue this task connected to.
    Only need to be specified if different from `settings.CELERY_TASK_DEFAULT_QUEUE`"""

    celery_task_revoked_queue: str = settings.CELERY_TASK_REVOKED_QUEUE
    """Name of the queue where revoked tasks are stored.
    Only need to be specified if different from `settings.CELERY_TASK_REVOKED_QUEUE`"""

    _celery_app: Celery | None = None

    class Meta:
        abstract = True
        default_permissions = (
            "add",
            "change",
            "delete",
            "view",
            "queue",
            "terminate",
            "inspect",
            "revoke",
        )

    def __str__(self):
        return self.description or f"Background Job #{self.pk}"

    @classproperty
    def celery_app(cls) -> "celery.app.base.Celery":  # noqa
        if not cls._celery_app:
            from celery import current_app as app

            cls._celery_app = app
        return cls._celery_app

    @property
    def celery_task_name(self):  # pragma: no cover
        return self.default_celery_task_name

    @classmethod
    def check(cls, **kwargs):
        errors = super().check(**kwargs)
        if not cls.celery_task_name:
            errors.append(
                checks.Warning(
                    "'%s' does not have a Celery task name." % cls._meta,
                    id="django_celery_boost.E001",
                )
            )
        else:
            try:
                import_string(cls.celery_task_name)
            except ImportError:
                errors.append(
                    checks.Error(
                        "'%s': Cannot import Celery task '%s'" % (cls._meta, cls.celery_task_name),
                        id="django_celery_boost.E002",
                    )
                )
            else:
                cls.celery_app.autodiscover_tasks()
                if cls.celery_task_name not in cls.celery_app.tasks:
                    errors.append(
                        checks.Error(
                            "'%s' is using a non registered Celery task. (%s)" % (cls._meta, cls.celery_task_name),
                            id="django_celery_boost.E003",
                        )
                    )

        return errors

    @classmethod
    def get_queue_entries(cls):
        with cls.celery_app.pool.acquire(block=True) as conn:
            return conn.default_channel.client.lrange(cls.celery_task_queue, 0, -1)

    @classmethod
    def get_queue_size(cls) -> "int":
        with cls.celery_app.pool.acquire(block=True) as conn:
            return int(conn.default_channel.client.llen(cls.celery_task_queue))

    @property
    def queue_position(self) -> int:
        """Return the position of the current task in the queue.

        Returns:
            int task position in queue

        """
        if self.is_terminated():
            return 0
        with self.celery_app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange(self.celery_task_queue, 0, -1)
        for i, task in enumerate(reversed(tasks), 1):
            j = json.loads(task)
            if j["headers"]["id"] == self.curr_async_result_id:
                return i
        return 0

    @classmethod
    def celery_queue_entries(cls) -> "Generator":
        with cls.celery_app.pool.acquire(block=True) as conn:
            yield from conn.default_channel.client.lrange(cls.celery_task_queue, 0, -1)

    @classmethod
    def celery_queue_info(cls) -> "dict[str, int]":
        """Return information about the queue.

        Returns:
            Dictionary with size,pending, canceled, revoked tasks

        """
        conn: Connection
        channel: Channel
        with cls.celery_app.pool.acquire(block=True) as conn:
            channel = conn.default_channel
            size = cls.get_queue_size()
            revoked = list(channel.client.smembers(cls.celery_task_revoked_queue))
            pending = size
            canceled = 0

            return {
                "size": size,
                "pending": pending,
                "canceled": canceled,
                "revoked": len(revoked),
            }

    @property
    def async_result(self) -> "AsyncResult|None":
        """Return the AsyncResult object of the current instance."""
        if self.curr_async_result_id:
            return AsyncResult(self.curr_async_result_id)
        return None

    @property
    def queue_entry(self) -> "dict[str, Any]":
        """Return the queue entry of the current instance."""
        if self.async_result:
            for task in self.celery_queue_entries():
                j = json.loads(task)
                if j["headers"]["id"] == self.async_result.id:
                    j["body"] = json.loads(base64.b64decode(j["body"]))
                    return j
        return {"id": "NotFound"}

    @property
    def task_info(self) -> "dict[str, Any]":
        """Return the task meta information of the current instance.

        Returns:
            Dictionary with task information

        """
        ret = {"status": self.task_status, "completed_at": ""}
        if self.async_result:
            info = self.async_result._get_task_meta()
            result, task_status = info["result"], info["status"]
            if task_status == self.SUCCESS:
                started_at = info.get("start_time", 0)
            else:
                started_at = "-"
            date_done = info.get("date_done", None)
            if isinstance(result, Exception):
                error = str(result)
            elif task_status == self.REVOKED:
                error = _("Query execution cancelled.")
            else:
                error = ""

            if task_status == self.SUCCESS and not error:
                query_result_id = result
            else:
                query_result_id = None
            return {
                **info,
                "started_at": started_at,
                "completed_at": date_done,
                "last_update": date_done,
                "status": task_status,
                "error": error,
                "query_result_id": query_result_id,
            }
        return ret

    @property
    def started(self) -> str:
        try:
            return self.task_info["started_at"]
        except KeyError:
            return "="

    @classproperty
    def task_handler(cls: "type[CeleryTaskModel]") -> "Callable[[Any], Any]":  # noqa
        """Return the task assigned to this model."""
        return import_string(cls.celery_task_name)

    def is_queued(self) -> bool:
        """Check if the job is queued."""
        try:
            with self.celery_app.pool.acquire(block=True) as conn:
                tasks = conn.default_channel.client.lrange(self.celery_task_queue, 0, -1)
            for task in tasks:
                j = json.loads(task)
                if j["headers"]["id"] == self.curr_async_result_id:
                    return True
        except Exception as e:
            logger.exception(e)
        return False

    def is_terminated(self) -> bool:
        """Check if the job is queued."""
        return self.task_status and self.task_status in self.TERMINATED_STATUSES

    def log_task_action(self, action, user):
        self.celery_history[str(timezone.now())] = f"{action} by {user}"
        self.save(update_fields=["celery_history"])

    @property
    def verbose_status(self) -> str:
        status = self.task_status
        if self.local_status:
            return f"{status} ({self.local_status})"
        return status

    @property
    def task_status(self) -> str:
        """Return the task status querying Celery API."""
        try:
            if self.curr_async_result_id:
                result = self.async_result.state
                if result == self.PENDING:
                    if self.is_queued():
                        result = self.QUEUED
                    else:
                        result = self.MISSING
            else:
                result = self.NOT_SCHEDULED
            return result
        except Exception as e:  # noqa
            return str(e)

    def queue(self, use_version: bool = True) -> str | None:
        """Queue the record processing.

        use_version: if True the task fails if the record is changed after it has been queued.
        """
        if self.task_status not in self.ACTIVE_STATUSES:
            res = self.task_handler.delay(self.pk, self.version if use_version else None)
            with concurrency_disable_increment(self):
                self.curr_async_result_id = res.id
                self.datetime_queued = timezone.now()
                self.save(update_fields=["curr_async_result_id", "datetime_queued"])
                task_queued.send(sender=self.__class__, task=self)
            return self.curr_async_result_id
        return None

    def revoke(self, wait=False, timeout=None) -> None:
        if self.async_result:
            self.async_result.revoke(terminate=False, signal="SIGTERM", wait=wait, timeout=timeout)
        task_revoked.send(sender=self.__class__, task=self)

    def terminate(self, wait=False, timeout=None) -> str:
        """Revoke the task. Does not need Running workers."""
        if self.task_status in ["QUEUED", "PENDING"]:
            with self.celery_app.pool.acquire(block=True) as conn:
                conn.default_channel.client.sadd(
                    self.celery_task_revoked_queue,
                    self.curr_async_result_id,
                    self.curr_async_result_id,
                )
                # removes the task from the queue
                for task_json in self.celery_queue_entries():
                    task = json.loads(task_json)
                    try:
                        if task.get("headers").get("id") == self.curr_async_result_id:  # pragma: no branch
                            conn.default_channel.client.lrem(self.celery_task_queue, 1, task_json)
                            break
                    except AttributeError:  # pragma: no cover
                        pass
                conn.default_channel.client.delete(f"celery-task-meta-{self.curr_async_result_id}")
            self.curr_async_result_id = None
            st = self.CANCELED
        elif self.async_result:
            self.async_result.revoke(terminate=True, signal="SIGKILL", wait=wait, timeout=timeout)
            st = self.REVOKED
        else:
            self.curr_async_result_id = None
            st = self.UNKNOWN

        self.local_status = st
        self.save(update_fields=["local_status", "curr_async_result_id"])
        task_terminated.send(sender=self.__class__, task=self)
        return st

    @classmethod
    def discard_all(cls: "type[CeleryTaskModel]") -> None:
        cls.celery_app.control.discard_all()
        cls.objects.update(curr_async_result_id=None)
        cls.purge()

    @classmethod
    def purge(cls: "type[CeleryTaskModel]") -> None:
        cls.celery_app.control.purge()
        with cls.celery_app.pool.acquire(block=True) as conn:
            conn.default_channel.client.delete(cls.celery_task_queue)
            conn.default_channel.client.delete(cls.celery_task_revoked_queue)


class AsyncJobModel(CeleryTaskModel):
    class JobType(models.TextChoices):
        STANDARD_TASK = "STANDARD_TASK", "Standard Task"
        JOB_TASK = "JOB_TASK", "Job Task"

    type = models.CharField(max_length=50, choices=JobType.choices)
    config = models.JSONField(default=dict, blank=True)
    action = models.CharField(max_length=500, blank=True, null=True)
    sentry_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        abstract = True
        permissions = (("debug_job", "Can debug background jobs"),)

    def execute(self):
        sid = None
        try:
            func = import_string(self.action)
            match self.type:
                case AsyncJobModel.JobType.STANDARD_TASK:
                    return func(**self.config)
                case AsyncJobModel.JobType.JOB_TASK:
                    return func(self)
        except Exception as e:
            sid = sentry_sdk.capture_exception(e)
            raise e
        finally:
            if sid:
                self.sentry_id = sid
                self.save(update_fields=["sentry_id"])
