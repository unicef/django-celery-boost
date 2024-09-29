# django-celery-model

[![Test](https://github.com/unicef/django-celery-model/actions/workflows/test.yml/badge.svg)](https://github.com/unicef/django-celery-model/actions/workflows/test.yml)
[![Lint](https://github.com/unicef/django-celery-model/actions/workflows/lint.yml/badge.svg)](https://github.com/unicef/django-celery-model/actions/workflows/lint.yml)
[![Documentation](https://github.com/unicef/django-celery-model/actions/workflows/docs.yml/badge.svg)](https://github.com/unicef/django-celery-model/actions/workflows/docs.yml)
[![codecov](https://codecov.io/github/unicef/django-celery-model/graph/badge.svg?token=L7HA5PJ45B)](https://codecov.io/github/unicef/django-celery-model)


django-celery-model is a small Django Abstract Model that provides some useful methods to manage 
Models that represents the "context" of a Celery task.  


!!! Note
    
    Django-celery-models is part of the UNICEF HOPE project, read more [here](https://unicef.github.io/hope-documentation/).



## Features

- Easy control Django Model records to celery task
- Business View of Celery Task 
- Revoke tasks with to running workers
- Retrieve task position in the queue
- Admin integration to inspect task status (running/result/error)
