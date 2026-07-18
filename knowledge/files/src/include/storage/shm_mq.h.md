# `storage/shm_mq.h`

- **Source:** `source/src/include/storage/shm_mq.h` (88 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public API for the SPSC shared-memory message queue. See `shm_mq.c.md`.

## Result codes

```
SHM_MQ_SUCCESS       /* sent or received */
SHM_MQ_WOULD_BLOCK   /* retry later (nowait mode) */
SHM_MQ_DETACHED      /* peer is gone */
```

## Typical usage

```c
/* Sized in advance via shm_mq_minimum_size + payload estimate */
shm_mq *mq = shm_mq_create(addr, size);
shm_mq_set_sender(mq, leader_proc);     /* once, by either side */
shm_mq_set_receiver(mq, worker_proc);   /* once, by either side */
shm_mq_handle *h = shm_mq_attach(mq, seg, bgw_handle);
shm_mq_send(h, nbytes, data, false, true);   /* blocking */
shm_mq_receive(h, &n, &p, false);            /* zero-copy in ring */
shm_mq_detach(h);
```

## iov-style send

`shm_mq_sendv(h, iov, iovcnt, …)` — gather-write multiple chunks
atomically (one length prefix, then all chunks concatenated). Used
by libpq message marshaling for parallel-query error queues.

## BackgroundWorkerHandle integration

Passing the worker's handle to `shm_mq_attach` enables detach detection
when the worker crashes mid-attach: `bgworker.c` notices the dead
worker and the queue marks itself detached.

## `shm_mq_minimum_size`

Constant exposed for callers sizing their DSM. Smaller than a single
useful message — you almost always want much more (8 KB+ typical).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)
