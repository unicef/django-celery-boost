import time

from celery import shared_task
from concurrency.exceptions import RecordModifiedError


@shared_task(bind=True)
def process_job(self, pk, version=None):
    from .models import Job

    job = Job.objects.get(pk=pk)

    if version and job.version != version:
        raise RecordModifiedError(f"Unexpected version {version}. It should be {job.version}", target=job)

    if job.op == "upper":
        job.name = job.name.upper()
    elif job.op == "progress":
        for i in range(1, job.value):
            self.update_state(state="PROGRESS", meta={"current": i})
            time.sleep(0.5)
    elif job.op == "loop":
        start = time.time()
        for i in range(job.value):
            time.sleep(1)
        elapsed = time.time() - start
        return {"loops": job.value, "elapsed": elapsed}

    elif job.op == "sleep":
        time.sleep(job.value)

    elif job.op == "raise":
        raise Exception(job.name)
    else:
        raise Exception("Unknown {op}")
    job.save()
    return job.name


@shared_task()
def echo(value):
    return value
