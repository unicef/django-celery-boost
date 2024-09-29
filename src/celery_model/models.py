import base64
import json
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional

from celery import states
from celery.app.base import Celery
from celery.result import AsyncResult
from concurrency.api import concurrency_disable_increment
from concurrency.fields import AutoIncVersionField
from django.conf import settings
from django.core import checks
from django.db import models
from django.utils.functional import classproperty
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

if TYPE_CHECKING:
    import celery.app.control
    from kombu.connection import Connection
    from kombu.transport.redis import Channel


class CeleryManager:
    pass


class CeleryTaskModel(models.Model):
    class Meta:
        abstract = True

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

    SCHEDULED = frozenset({states.PENDING, states.RECEIVED, states.STARTED, states.RETRY, QUEUED})

    version = AutoIncVersionField()

    last_run = models.DateTimeField(null=True, blank=True)
    curr_async_result_id = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        help_text="Current (active) AsyncResult is",
    )
    last_async_result_id = models.CharField(
        max_length=36, blank=True, null=True, help_text="Latest executed AsyncResult is"
    )
    history = models.JSONField(default=dict, blank=True, null=False)
    result = models.CharField(max_length=100, default="", blank=True, null=True)

    celery_task_name: str = ""
    celery_task_queue: str = settings.CELERY_TASK_DEFAULT_QUEUE
    celery_task_revoked_queue: str = settings.CELERY_TASK_REVOKED_QUEUE
    _celery_app: Optional[Celery] = None

    @classproperty
    def celery_app(cls) -> "celery.app.base.Celery":
        if not cls._celery_app:
            from celery import current_app as app
            cls._celery_app = app
        return cls._celery_app

    @classmethod
    def check(cls, **kwargs):
        errors = super().check(**kwargs)
        if not cls.celery_task_name:
            errors.append(
                checks.Error(
                    "'%s' does not have a Celery task name." % cls._meta,
                    id="celery_model.E001",
                )
            )
        else:
            try:
                import_string(cls.celery_task_name)
            except ImportError:
                errors.append(
                    checks.Error(
                        "'%s': Cannot import Celery task '%s'" % (cls._meta, cls.celery_task_name),
                        id="celery_model.E002",
                    )
                )
            else:
                cls.celery_app.autodiscover_tasks()
                if cls.celery_task_name not in cls.celery_app.tasks.keys():
                    errors.append(
                        checks.Error(
                            "'%s' is using a non registered Celery task. (%s)" % (cls._meta, cls.celery_task_name),
                            id="celery_model.E003",
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
        """
        Returns the position of the current task in the queue.

        Returns:
            int task position in queue
        """
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
            for entry in conn.default_channel.client.lrange(cls.celery_task_queue, 0, -1):
                yield entry
            # return conn.default_channel.client.llen(cls.celery_task_queue)

    @classmethod
    def celery_queue_info(cls) -> "dict[str, int]":
        """ Returns information about the Queue

        Returns:
            Dictionary with size,pendig, canceled, revoked tasks
        """

        conn: Connection
        channel: Channel
        with cls.celery_app.pool.acquire(block=True) as conn:
            channel = conn.default_channel
            # size = channel.client.llen(cls.celery_task_queue)
            size = cls.get_queue_size()
            # tasks = channel.client.lrange(cls.celery_task_queue, 0, size)
            # tasks = list(cls.celery_queue_entries())
            revoked = list(channel.client.smembers(cls.celery_task_revoked_queue))
            pending = size
            canceled = 0
            pending_tasks = [json.loads(task)["headers"]["id"].encode() for task in cls.celery_queue_entries()]
            # for task_id in pending_tasks:
            #     if task_id in revoked:
            #         pending -= 1
            #         canceled += 1

            for rem in revoked:
                if rem not in pending_tasks:
                    channel.client.srem(cls.celery_task_revoked_queue, rem)
            return {
                "size": size,
                "pending": pending,
                "canceled": canceled,
                "revoked": len(revoked),
            }

    @property
    def async_result(self) -> "AsyncResult|None":
        """ Returns the AsyncResult object of the current instance"""
        if self.curr_async_result_id:
            return AsyncResult(self.curr_async_result_id)
        else:
            return None

    @property
    def queue_entry(self) -> "dict[str, Any]":
        """ Returns the queue entry of the current instance"""
        if self.async_result:
            for task in self.celery_queue_entries():
                j = json.loads(task)
                if j["headers"]["id"] == self.async_result.id:
                    j["body"] = json.loads(base64.b64decode(j["body"]))
                    return j
        return {"id": "NotFound"}

    @property
    def task_info(self) -> "dict[str, Any]":
        """ Returns the task meta information of the current instance

        Returns:
            Dictionary with task information
        """
        ret = {"status": self.status}
        if self.async_result:
            info = self.async_result._get_task_meta()
            result, task_status = info["result"], info["status"]
            if task_status == self.SUCCESS:
                started_at = info.get("start_time", 0)
            else:
                started_at = 0
            last_update = info.get("date_done", None)
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
                # "id": self.async_result.id,
                "last_update": last_update,
                "started_at": started_at,
                "status": task_status,
                "error": error,
                "query_result_id": query_result_id,
            }
        return ret

    @classproperty
    def task_handler(cls: "type[CeleryTaskModel]") -> "Callable[[Any], Any]":
        """ Return the task assigned to this model """
        return import_string(cls.celery_task_name)

    def is_queued(self) -> bool:
        """ Check if the job is queued  """
        with self.celery_app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange(self.celery_task_queue, 0, -1)
        for task in tasks:
            j = json.loads(task)
            if j["headers"]["id"] == self.curr_async_result_id:
                return True
        return False

    def is_canceled(self) -> bool:
        if self.curr_async_result_id:
            with self.celery_app.pool.acquire(block=True) as conn:
                return (
                    conn.default_channel.client.sismember(self.celery_task_revoked_queue, self.curr_async_result_id) > 0
                )
        return False

    @property
    def status(self) -> str:
        """ Returns the task status querying Celery API"""
        try:
            if self.curr_async_result_id:
                if self.is_canceled():
                    return self.CANCELED

                result = self.async_result.state
                if result == self.PENDING:
                    if self.is_queued():
                        result = self.QUEUED
                    else:
                        result = self.MISSING
            else:
                result = self.NOT_SCHEDULED
            return result
        except Exception as e:
            return str(e)

    def queue(self) -> str | None:
        """ Queue the record processing"""
        if self.status not in self.SCHEDULED:
            res = self.task_handler.delay(self.pk, self.version)
            with concurrency_disable_increment(self):
                self.curr_async_result_id = res.id
                self.save(update_fields=["curr_async_result_id"])
            return self.curr_async_result_id
        return None

    def terminate(self) -> str:
        """ Revoke the task. Does not need Running workers"""
        st = self.UNKNOWN
        if self.status in ["QUEUED", "PENDING"]:
            with self.celery_app.pool.acquire(block=True) as conn:
                conn.default_channel.client.sadd(
                    self.celery_task_revoked_queue,
                    self.curr_async_result_id,
                    self.curr_async_result_id,
                )
                for task_json in self.celery_queue_entries():
                    task = json.loads(task_json)
                    try:
                        if task.get('headers').get('id') == self.curr_async_result_id:
                            conn.default_channel.client.lrem(self.celery_task_queue, 1, task_json)
                            break
                    except AttributeError:  # pragma: no cover
                        pass
                conn.default_channel.client.delete(f"celery-task-meta-{self.curr_async_result_id}")
            st = self.CANCELED
        elif self.async_result:
            self.celery_app.control.revoke(self.curr_async_result_id, terminate=True, signal="SIGKILL")
            st = self.REVOKED
        self.result = st
        self.save(update_fields=["result"])
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
