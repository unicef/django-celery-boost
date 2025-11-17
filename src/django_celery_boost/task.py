from typing import Any, Protocol, cast

from celery import Task
from celery.result import EagerResult, AsyncResult
from django.apps import apps


class ApplyCallable[T: AsyncResult](Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> T: ...


def _apply[T: AsyncResult](apply_method: ApplyCallable[T], *args: Any, **kwargs: Any) -> T:
    from django_celery_boost.models import APP_LABEL, MODEL_NAME, CeleryTaskModel

    task_args = args[0]
    pk, version = task_args[-2], task_args[-1]
    task_kwargs = args[1]
    app_label, model_name = task_kwargs[APP_LABEL], task_kwargs[MODEL_NAME]

    model_class = cast(type[CeleryTaskModel], apps.get_model(app_label, model_name))
    model = model_class.objects.get(pk=pk, version=version)

    # we want pk and version to always come first
    new_task_args = task_args[-2:] + task_args[:-2]
    # We can possibly check whether the task is in an active state, if it's
    # required, it can be done by passing some flag in kwargs and raising an
    # exception in the overridden run method. Other options could require much
    # more work
    new_task_kwargs: dict[str, Any] = {}

    new_args: tuple[Any, ...] = (new_task_args, new_task_kwargs) + args[2:]
    result = apply_method(*new_args, **kwargs)
    model.set_queued(result)
    return result


class TaskRunFromSignature(Task):
    def apply(self, *args: Any, **kwargs: Any) -> EagerResult:
        return _apply(super().apply, *args, **kwargs)

    def apply_async(self, *args: Any, **kwargs: Any) -> AsyncResult:
        return _apply(super().apply_async, *args, **kwargs)
