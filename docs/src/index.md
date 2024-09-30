---
title: Documentation
---

django-celery-boost is a small Django Abstract Model that provides some useful methods to manage 
Models that represents the "context" of a Celery task.  

django-celery-boost is part of the UNICEF HOPE project, read more [here](https://unicef.github.io/hope-documentation/).


!!! warning

    Currently only Redis backed is supported


## Features

- Easy control Django Model records to celery task
- Business View of Celery Task 
- Revoke tasks with to running workers
- Retrieve task position in the queue
- Admin integration to inspect task status (running/result/error)
