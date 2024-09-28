# Best Practices


# Bind your tasks

Inform what is happening inside your task

    @celery.task(bind=True)
    def long_task(self):
        record = 1

        for entry in Model.objects.all():
            self.update_state(state='PROGRESS', meta={'current': record, 'entry': str(entry)})
            record += 1
