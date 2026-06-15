# src/test/modules/test_shm_mq/worker.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 192
**Verification depth:** full read

## Role

The per-worker background-worker main loop: attaches to the DSM segment and TOC
passed by the registering backend, claims a worker number, attaches to its
inbound and outbound queues, signals readiness, then copies messages from
inbound to outbound until a queue detaches. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:48-138`

## Public API

- `test_shm_mq_main(Datum main_arg)` — bgworker entrypoint named in
  `bgw_function_name`; `main_arg` is the DSM segment handle. Marked
  `pg_noreturn` (calls `proc_exit`). [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:48-49,137`

## Invariants

- INV-1: A worker reads from queue key `myworkernumber` and writes to queue key
  `myworkernumber + 1` — adjacent links in the ring. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:156-160`
- INV-2: `++workers_attached` (the assigned worker number) must not exceed
  `workers_total`, else ERROR — guards against an extra worker attaching. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:96-102`
- INV-3: `workers_attached`/`workers_ready` mutations happen under
  `hdr->mutex`. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:96-98,118-120`
- INV-4: Once a worker bumps `workers_ready` and signals the registrant, the
  user backend may assume on_dsm_detach callbacks fire before the worker
  detaches — so all DSM structures must be attached before signaling. [from-comment] `source/src/test/modules/test_shm_mq/worker.c:109-120`

## Notable internals

- `BackgroundWorkerUnblockSignals` first; standard handlers suffice. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:60`
- `dsm_attach(DatumGetUInt32(main_arg))` then `shm_toc_attach` with
  `PG_TEST_SHM_MQ_MAGIC`; both NULL returns are ERRORs. No ResourceOwner is
  created, so the mapping survives until process exit (intentional). [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:71-85`
- Header located at TOC key 0; worker number assigned by atomic increment under
  spinlock. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:87-102`
- `attach_to_queues` sets this proc as receiver of the inbound queue and sender
  of the outbound queue, attaching with NULL handle (no peer-handle needed). [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:149-162`
- After signaling, the registrant proc is found via
  `BackendPidGetProc(MyBgworkerEntry->bgw_notify_pid)`; if it has exited the
  worker logs DEBUG1 and `proc_exit(1)`s, otherwise `SetLatch` on its
  `procLatch`. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:121-127`
- `copy_messages` loops: `CHECK_FOR_INTERRUPTS`, blocking `shm_mq_receive`,
  blocking `shm_mq_send`; any non-`SHM_MQ_SUCCESS` (i.e. detach) breaks the
  loop, driving cascading shutdown. [verified-by-code] `source/src/test/modules/test_shm_mq/worker.c:171-192`

## Cross-refs

- `source/src/test/modules/test_shm_mq/setup.c` — registers the worker, lays out
  the queues this worker attaches to.
- `source/src/backend/storage/ipc/shm_mq.c` — `shm_mq_attach`,
  `shm_mq_set_sender`/`set_receiver`, `shm_mq_send`/`receive`.
- `source/src/backend/storage/ipc/shm_toc.c` — `shm_toc_attach`,
  `shm_toc_lookup`.
- `source/src/backend/storage/ipc/dsm.c` — `dsm_attach`/`dsm_detach`.
- `source/src/backend/storage/lmgr/proc.c` / `procarray.c` —
  `BackendPidGetProc`, `procLatch`.

## Potential issues

- **[ISSUE-question: workers_total read outside spinlock]** `worker.c:99` — the
  `myworkernumber > hdr->workers_total` comparison reads `workers_total` after
  releasing `hdr->mutex` at line 98. `workers_total` is written once in setup
  before any worker starts and never mutated afterward, so this is safe in
  practice; flagging only because the surrounding counter accesses are all
  mutex-protected and the asymmetry could mislead a reader. Severity: nit.
