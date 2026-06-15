# src/test/modules/test_shm_mq/test.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 274
**Verification depth:** full read

## Role

Provides the two SQL-callable entry points of the module (`test_shm_mq`,
`test_shm_mq_pipelined`) which set up the worker ring via `test_shm_mq_setup`,
push a message around it `loop_count` times, and verify the round-tripped
message is byte-identical to the original. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:44-121,133-254`

## Public API

- `test_shm_mq(queue_size, message, loop_count, nworkers)` — blocking
  round-trip test; requires `nworkers >= 1` (can't send to itself with blocking
  interface). [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:44-121`
- `test_shm_mq_pipelined(queue_size, message, loop_count, nworkers, verify)` —
  nonblocking pipelined test; allows `nworkers == 0` (can send to self),
  interleaves send and receive to avoid deadlock when the ring fills. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:133-254`
- `PG_MODULE_MAGIC` and both `PG_FUNCTION_INFO_V1` declarations. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:25-28`

## Invariants

- INV-1: `loop_count < 0` is rejected in both functions. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:61-64,153-156`
- INV-2: blocking test requires `nworkers > 0`; pipelined test requires
  `nworkers >= 0`. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:71-74,162-165`
- INV-3: pipelined loop terminates only when `receive_count == loop_count`, and
  asserts `send_count == receive_count` at that point (else internal error). [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:217-228`
- INV-4: a `SHM_MQ_WOULD_BLOCK` from `shm_mq_send` must be retried with the same
  message size and contents on the next call — satisfied trivially here because
  the same message is resent each time. [from-comment] `source/src/test/modules/test_shm_mq/test.c:175-181`

## Notable internals

- `test_shm_mq` sends once (blocking, `nowait=false`) then loops:
  `shm_mq_receive` → break on last iteration → `shm_mq_send`. Final
  `verify_message`, then `dsm_detach`. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:80-118`
- `test_shm_mq_pipelined` uses nonblocking send/receive (`nowait=true`),
  tracking `send_count`/`receive_count`; when no progress is made it sleeps on
  `MyLatch` with the custom `TestShmMqMessageQueue` wait event +
  `WL_EXIT_ON_PM_DEATH`, then `ResetLatch` + `CHECK_FOR_INTERRUPTS`. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:171-248`
- `SHM_MQ_DETACHED` from either send or receive is escalated to ERROR;
  `SHM_MQ_WOULD_BLOCK` just leaves `wait = true`. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:191-194,212-215`
- `verify_message` compares lengths then byte-by-byte, raising "message
  corrupted" with an errdetail pinpointing the differing byte. [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:259-274`
- Message payload extracted with `VARDATA_ANY` / `VARSIZE_ANY_EXHDR` (toast-safe
  via `PG_GETARG_TEXT_PP`). [verified-by-code] `source/src/test/modules/test_shm_mq/test.c:48-50,137-139`

## Cross-refs

- `source/src/test/modules/test_shm_mq/setup.c` — `test_shm_mq_setup`.
- `source/src/backend/storage/ipc/shm_mq.c` — `shm_mq_send`, `shm_mq_receive`,
  `shm_mq_result` codes.
- `source/src/backend/storage/ipc/dsm.c` — `dsm_detach`.
- `source/src/backend/utils/activity/wait_event.c` — `WaitEventExtensionNew`.

## Potential issues

None.
