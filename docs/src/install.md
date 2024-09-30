---
title: Install
---

django-celery-boost is a small Django Abstract Model that provides some useful methods to manage 
Models that represents the "context" of a Celery task.  


!!! warning

    Currently only Redis backed is supported


## Install

    pip install django-celery-boost

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
