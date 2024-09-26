from time import sleep

from demo.models import Job

from .celery import app


@app.task()
def process_job(pk, version):
    job = Job.objects.get(pk=pk, version=version)
    job.name = job.name.upper()
    job.save()
    return job.name.upper()


@app.task()
def stuck_job(pk, version):
    sleep(1000)
