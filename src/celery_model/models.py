import base64
import json
from typing import Any, Callable

from celery import current_app as app
from celery import states
from celery.result import AsyncResult
from concurrency.api import disable_concurrency
from concurrency.fields import AutoIncVersionField
from django.conf import settings
from django.core import checks
from django.db import models
from django.db.models import Model
from django.utils.functional import classproperty
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _


class CeleryTaskModel(models.Model):
    class Meta:
        abstract = True

    STARTED = states.STARTED  # (task has been started)
    SUCCESS = states.SUCCESS  # (task executed successfully)
    PENDING = states.PENDING  # (waiting for execution or unknown task id)
    FAILURE = states.FAILURE  # (task execution resulted in exception)
    RETRY = states.RETRY  # (task is being retried)
    REVOKED = states.REVOKED  # (task has been revoked)
    QUEUED = "QUEUED"  # (task exists in Redis but unknown to Celery)
    CANCELED = "CANCELED"  # (task is canceled BEFORE worker fetch it)
    NOT_SCHEDULED = "Not scheduled"
    MISSING = "MISSING"  # Task seems scheduled (it has a ResultID, but is not present in Celery)

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

    celery_task_name: str = ""

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
                from celery import current_app

                current_app.autodiscover_tasks()
                if cls.celery_task_name not in current_app.tasks.keys():
                    errors.append(
                        checks.Error(
                            "'%s' is using a non registered Celery task. (%s)" % (cls._meta, cls.celery_task_name),
                            id="celery_model.E003",
                        )
                    )

        return errors

    def get_celery_queue_position(self) -> int:
        with app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange(settings.CELERY_TASK_DEFAULT_QUEUE, 0, -1)
        for i, task in enumerate(reversed(tasks), 1):
            j = json.loads(task)
            if j["headers"]["id"] == self.curr_async_result_id:
                return i
        return 0

    @classmethod
    def celery_queue_status(cls) -> "dict[str, int]":
        with app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange(settings.CELERY_TASK_DEFAULT_QUEUE, 0, 1)
            revoked = list(conn.default_channel.client.smembers(settings.CELERY_TASK_REVOKED_QUEUE))
            pending = len(tasks)
            canceled = 0
            pending_tasks = [json.loads(task)["headers"]["id"].encode() for task in tasks]
            for task_id in pending_tasks:
                if task_id in revoked:
                    pending -= 1
                    canceled += 1

            for rem in revoked:
                if rem not in pending_tasks:
                    conn.default_channel.client.srem(settings.CELERY_TASK_REVOKED_QUEUE, rem)
            return {
                "size": len(tasks),
                "pending": pending,
                "canceled": canceled,
                "revoked": len(revoked),
            }

    @property
    def async_result(self) -> "AsyncResult|None":
        if self.curr_async_result_id:
            return AsyncResult(self.curr_async_result_id)
        else:
            return None

    @property
    def queue_info(self) -> "dict[str, Any]":
        with app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange(settings.CELERY_TASK_DEFAULT_QUEUE, 0, -1)

        if self.async_result:
            for task in tasks:
                j = json.loads(task)
                if j["headers"]["id"] == self.async_result.id:
                    j["body"] = json.loads(base64.b64decode(j["body"]))
                    return j
        return {"id": "NotFound"}

    @property
    def task_info(self) -> "dict[str, Any]":
        if self.async_result:
            info = self.async_result._get_task_meta()
            result, task_status = info["result"], info["status"]
            if task_status == self.SUCCESS:
                started_at = result.get("start_time", 0)
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

    @classproperty
    def task_handler(cls) -> "Callable[[Any], Any]":
        return import_string(cls.celery_task_name)

    def is_queued(self) -> bool:
        from celery import current_app as app

        with app.pool.acquire(block=True) as conn:
            tasks = conn.default_channel.client.lrange(settings.CELERY_TASK_DEFAULT_QUEUE, 0, -1)
        for task in tasks:
            j = json.loads(task)
            if j["headers"]["id"] == self.curr_async_result_id:
                return True
        return False

    def is_canceled(self) -> bool:
        with app.pool.acquire(block=True) as conn:
            return conn.default_channel.client.sismember(settings.CELERY_TASK_REVOKED_QUEUE, self.curr_async_result_id)

    @property
    def status(self) -> str:
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
        if self.status not in self.SCHEDULED:
            # ver = self.version
            res = self.task_handler.delay(self.pk, self.version)
            with disable_concurrency(self):
                self.curr_async_result_id = res.id
                self.save(update_fields=["curr_async_result_id"])
            # assert self.version == ver
            return self.curr_async_result_id
        return None

    def terminate(self) -> str:
        if self.status in ["QUEUED", "PENDING"]:
            with app.pool.acquire(block=True) as conn:
                conn.default_channel.client.sadd(
                    settings.CELERY_TASK_REVOKED_QUEUE,
                    self.curr_async_result_id,
                    self.curr_async_result_id,
                )
            return self.CANCELED
        elif self.async_result:
            return self.async_result.revoke(terminate=True)
        return ""

    @classmethod
    def discard_all(cls: "type[Model]") -> None:
        app.control.discard_all()
        cls.objects.update(curr_async_result_id=None)
        with app.pool.acquire(block=True) as conn:
            conn.default_channel.client.delete(settings.CELERY_TASK_REVOKED_QUEUE)

    @classmethod
    def purge(cls: "type[Model]") -> None:
        app.control.purge()
