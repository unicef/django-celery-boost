---
title: Install
---

django-celery-boost is a small Django Abstract Model that provides some useful methods to manage
Models that represents the "context" of a Celery task.


!!! warning

    Currently only Redis backed is supported


## Install

    pip install django-celery-boost

## Setup

In your `settings.py`:

    from <app>.config import env

    INSTALLED_APPS = [
        ...
        "admin_extra_buttons",
        "django_celery_boost",
    ]

    CELERY_BROKER_URL=redis://
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL
    CELERY_TASK_IGNORE_RESULT = False
    CELERY_TASK_DEFAULT_QUEUE = "my_tasks_queue"
    CELERY_TASK_REVOKED_QUEUE = "my_revoked_queue"

    CELERY_BOOST_FLOWER = "/flower"  # optional, this is the default

## Flower links

When a task has a result id, `django-celery-boost` renders a **Flower** button
pointing to `<address>/task/<id>`. The address is resolved, in order, from:

1. `CELERY_BOOST_FLOWER` (canonical setting)
2. `CELERY_FLOW_ADDRESS` (deprecated alias, will be removed)
3. `/flower` (default)

A relative value is made absolute against the current request, so the link
automatically follows the host and scheme the admin is served from. Set an
absolute value only when Flower is hosted elsewhere:

    CELERY_BOOST_FLOWER = "https://flower.example.org"

To make the link available on **every** admin template (including the change
form), register the bundled context processor:

    TEMPLATES = [
        {
            ...
            "OPTIONS": {
                "context_processors": [
                    ...
                    "django_celery_boost.context_processors.flower",
                ],
            },
        },
    ]

It exposes `{{ flower_addr }}` to templates. The action pages (inspect, queue,
terminate) provide it out of the box.

## Use in your code

In your `tasks.py`

    from celery import current_app

    @current_app.task(bind=True)
    def process_job(self, pk, version=None):
        job = Job.objects.get(pk=pk)
        ...

In your `models.py`


    class Job(CeleryTaskModel, models.Model):
        ...

        celery_task_name = "demo.tasks.process_job"

        # optional in csse
        celery_task_queue = ...
        celery_task_revoked_queue = ...



!!! warning

    Due to how Meta inheritance works in Django, you must use `class Meta(CeleryTaskModel.Meta)`
    in case tou need to customize your concrete class's Meta. Es:


        class Meta(CeleryTaskModel.Meta):
            verbose_name = "Job"



To "run" your task:

    j = Job.objecs.get(pk=1)
    j.queue()

To cancel a task (soft revoke):

    j.revoke()

To stop a queued or running task (hard):

    j.terminate()

## Recover a task stuck after worker loss

If a worker dies while a task is `STARTED`, the result stays `STARTED` and the
task can no longer be queued. Use `revoke()` to detach the stale result, then
queue it again:

    j.revoke()
    j.queue()

`revoke()` broadcasts a soft Celery revoke, clears `curr_async_result_id` and the
local status (returning the task to `Not scheduled`) and forgets the stored
result. It does **not** kill a task that is still running; use `terminate()` for a
hard stop. In the admin these are the **Revoke** and **Terminate** buttons. See
[Concurrency and locks](concurrency.md) for details.
