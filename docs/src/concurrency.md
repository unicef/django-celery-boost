---
title: Concurrency and locks
---

# Concurrency and locks

django-celery-boost **does not acquire distributed locks, file locks, or database
row locks**. There is nothing to release, and a worker that dies cannot leave a
lock behind.

Instead, the library relies on two mechanisms:

- **Optimistic concurrency control (OCC)** through
  [`django-concurrency`](https://django-concurrency.readthedocs.io/): every
  concrete model gets a `version` field (`AutoIncVersionField`) that is
  incremented on save. The generated `UPDATE` is filtered by the previous
  version; if another writer committed in the meantime, the update matches no
  row and `RecordModifiedError` is raised.
- **A version check inside the task**: `queue()` sends the record `version` to
  the task, and the task re-fetches the record with `objects.get(pk=pk, version=version)`.
  A stale worker processing an outdated message raises `RecordModifiedError`
  instead of writing over newer data.

This is why a task left in `STARTED` after its worker died is **not** a held
lock — it is a stale value in the result backend. See [Recovering a stuck
task](#recovering-a-stuck-task).

!!! note

    `group_key` exists as a field, but it is **not enforced** by this library.
    Tasks sharing a `group_key` are *not* currently serialized. If you need
    mutual exclusion, add a lock yourself (see below).

## Recovering a stuck task

If a worker is lost while a task is `STARTED`, the result backend keeps reporting
`STARTED` forever. `queue()` refuses to run active tasks, so the record is stuck.
Use `reset()` to detach the stale result:

    job.reset()   # clears curr_async_result_id, local_status and tracking
    job.queue()   # now it can be scheduled again

`reset()` does not stop a running task. Only call it once the task is no longer
running (for example after a worker crash), or accept that its `AsyncResult` is
detached. The admin exposes the same operation as the **Reset** button.

## When you do need a lock

Decide first *why* you need mutual exclusion:

- **Efficiency** — running the task twice only wastes resources. An approximate
  lock is fine.
- **Correctness** — two runs would corrupt data. A time-to-live lease alone is
  not enough; you need a fencing token and a resource that rejects stale writes.

| Approach | Released on worker death | Long-running tasks | Notes |
| --- | --- | --- | --- |
| OCC / `version` + idempotent task | Yes (nothing held) | Yes | What this library provides |
| Redis lease (`SET NX PX` + token-checked release) | Yes, via TTL | Yes, with `extend` | Best-effort; not safe without fencing |
| `select_for_update` in `atomic()` | Yes (rollback/connection close) | No | Holds a DB connection; short critical sections only |
| PostgreSQL advisory lock | Yes (connection close) | No | Single DB; breaks under transaction-mode poolers |
| ZooKeeper / etcd lock + fencing token | Yes | Yes | Safe for correctness; heavyweight |

A minimal safe Redis lease:

    import uuid
    from django.core.cache import cache

    def run_exclusive(key, ttl=3600, **kwargs):
        token = uuid.uuid4().hex
        lock = cache.lock(f"lock:{key}", timeout=ttl)
        if not lock.acquire(blocking=False, token=token):
            return False  # someone else holds it; reschedule instead of blocking
        try:
            do_the_work(**kwargs)
        finally:
            # only releases if the token still matches (django-redis does this)
            lock.release()

Rules of thumb:

- Always set a TTL so a crashed holder self-heals.
- Acquire with `blocking=False` (or a short timeout) and re-queue on failure
  rather than tying up a worker.
- Extend the lease from inside long tasks, or set a TTL comfortably longer than
  the worst-case runtime.
- Make tasks [idempotent](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
  — with `task_acks_late`, a task may run more than once.
- If a stale write must be rejected, use a monotonic fencing token. The model
  `version` field is a natural candidate.

!!! warning

    Redis locks built only on a TTL are not safe for correctness. Process
    pauses (GC, paging) and clock jumps can let two holders believe they own the
    lock. If correctness depends on the lock, use a consensus-backed lock
    (ZooKeeper, etcd) and fencing tokens — see Martin Kleppmann's
    ["How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html).
