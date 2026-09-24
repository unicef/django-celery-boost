---
title: Concurrency and locks
---

# Concurrency and locks

django-celery-boost does **not** use distributed, file, or database row locks.
Nothing needs releasing, and a dead worker cannot leave a lock behind.

Instead it relies on optimistic concurrency control:

- Each model has a `version` (`AutoIncVersionField`, from `django-concurrency`)
  incremented on save. An `UPDATE` filtered by the previous version matches no
  row if another writer committed first, raising `RecordModifiedError`.
- `queue()` passes that `version` to the task, which re-fetches the record with
  `objects.get(pk=pk, version=version)`, so a stale worker cannot overwrite newer
  data.

A task left `STARTED` after worker loss is therefore just stale result-backend
state, not a held lock. See [Recovering a stuck task](#recovering-a-stuck-task).

!!! note

    `group_key` exists as a field but is **not enforced**. Tasks sharing a
    `group_key` are not serialized.

## Recovering a stuck task

If a worker dies while a task is `STARTED`, `queue()` refuses to run it and the
record is stuck. `revoke()` broadcasts the cancellation and detaches the stale
result:

    job.revoke()   # clears curr_async_result_id, status and tracking
    job.queue()    # can be scheduled again

`revoke()` is soft and does not kill a running task; use `terminate()` for that.
The admin exposes the same actions as **Revoke** and **Terminate**.

## When you need a lock

Decide whether overlapping runs are **wasteful** (efficiency) or **corrupting**
(correctness). A TTL lease is fine for the former; the latter needs fencing.

| Approach | Self-heals on worker death | Long tasks | Correctness |
| --- | --- | --- | --- |
| OCC / `version` + idempotent task | Yes | Yes | Strong (no lock held) |
| Redis lease (`cache.lock`, TTL + token) | Yes, via TTL | Yes, with `extend` | Best-effort |
| `select_for_update` in `atomic()` | Yes | No | Short critical sections only |
| ZooKeeper / etcd + fencing token | Yes | Yes | Safe |

Rules: always set a TTL; acquire non-blocking and re-queue on failure; make tasks
[idempotent](https://docs.celeryq.dev/en/stable/userguide/tasks.html); use the
`version` as a fencing token when stale writes must be rejected.

!!! warning

    TTL-only Redis locks are not safe for correctness under process pauses or
    clock jumps. See Kleppmann's
    ["How to do distributed locking"](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html).
