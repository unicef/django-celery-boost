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

    CELERY_BOOST_FLOWER = "<your flower address if available>"

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

To "cancel" it:

    j.terminate()
