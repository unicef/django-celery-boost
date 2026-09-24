# Best Practices


!!! note "General best practices"

    - Always return any "readable" value (es. True)
    - Uses [Persistent revokes](https://docs.celeryq.dev/en/stable/userguide/workers.html#worker-persistent-revokes)


## Task lifecycle actions

The library exposes several actions that are easy to confuse. They are not
interchangeable:

| Action | What it does | Stops a running task? |
| --- | --- | --- |
| `revoke()` | Broadcasts a soft Celery revoke and detaches the AsyncResult (`curr_async_result_id` cleared) so the record can be queued again. | No |
| `terminate()` | Removes a queued task from Redis, or sends a `SIGKILL`-terminate revoke to a running task, then detaches. | Yes |
| `request_cancellation()` | Sets a Redis flag the task must poll via `is_termination_requested`; the task then calls `cancel()` itself. | Cooperative |
| `cancel()` | Called *inside* the task to acknowledge a cancellation request (`local_status = CANCELED`). | N/A |

See [Concurrency and locks](concurrency.md#recovering-a-stuck-task) for the
worker-loss recovery recipe.

## Idempotency and concurrency

Celery guarantees *at-least-once* delivery (and with `task_acks_late=True` a task
may be redelivered after a worker crash), so tasks should be **idempotent**.

django-celery-boost adds optimistic concurrency control: each model has a
`version`, and `queue()` passes it to the task. The task re-fetches the record by
`(pk, version)`, so a task operating on stale data raises `RecordModifiedError`
instead of overwriting newer changes. Handle that exception explicitly (skip,
log, or re-queue) rather than swallowing it.

## Display progress

Inform what is happening inside your task

    @celery.task(bind=True)
    def long_task(self)-> bool:
        record = 1

        for entry in Model.objects.all():
            self.update_state(state='PROGRESS', meta={'current': record, 'entry': str(entry)})
            record += 1
        return True


## Sentry Integration

In case you use [Sentry](https://sentry.io/), add some useful information

    from functools import wraps

    def sentry_tags(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with configure_scope() as scope:
                scope.set_tag("celery", True)
                scope.set_tag("celery_task", func.__name__)
                return func(*args, **kwargs)

        return wrapper

    @celery.task(bind=True)
    @sentry_tags
    def task(self) -> bool:
        ...
        return True
