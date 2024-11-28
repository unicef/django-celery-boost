from django.dispatch import Signal

# actions
task_queued = Signal()
task_revoked = Signal()
task_terminated = Signal()

# events
task_complete = Signal()
task_start = Signal()
