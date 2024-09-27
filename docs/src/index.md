---
title: Documentation
---

django-celery-models is a small Django Abstract Model that provides some useful methods to manage 
Models that represents the "context" of a Celery task.  


## Install

    pip install django-celery-model

In your `settings.py`:
    
    from <app>.config import env

    INSTALLED_APPS = [
        ...
        "django_celery_beat",
        "admin_extra_buttons",
        "celery_model",
    ]
    
    CELERY_BROKER_URL=redis:// 
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL
    CELERY_TASK_IGNORE_RESULT = False



!!! warning

    Currently only Redis backed is supported
