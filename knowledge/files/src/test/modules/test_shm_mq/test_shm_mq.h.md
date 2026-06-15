# src/test/modules/test_shm_mq/test_shm_mq.h

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 45
**Verification depth:** full read

## Role

Shared header for the module: declares the TOC magic number, the control
structure (`test_shm_mq_header`) stored in the DSM segment, and the two
cross-file function prototypes (`test_shm_mq_setup`, `test_shm_mq_main`) that
bind setup.c, test.c, and worker.c together. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:21-44`

## Public API

- `PG_TEST_SHM_MQ_MAGIC` (`0x79fb2447`) — magic passed to
  `shm_toc_create`/`shm_toc_attach` to validate the segment. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:22`
- `test_shm_mq_header` — `{ slock_t mutex; int workers_total; int
  workers_attached; int workers_ready; }`; the control region at TOC key 0. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:29-35`
- `test_shm_mq_setup(...)` — prototype implemented in setup.c. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:38-40`
- `test_shm_mq_main(Datum)` — bgworker entrypoint prototype; `pg_noreturn` +
  `PGDLLEXPORT` so it can be resolved as a bgworker function symbol. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:43`

## Invariants

- INV-1: All three counters in `test_shm_mq_header` are guarded by `mutex`
  (a `slock_t` spinlock) by the convention enforced in setup.c/worker.c. [inferred] `source/src/test/modules/test_shm_mq/test_shm_mq.h:31-34`
- INV-2: `test_shm_mq_main` never returns (it `proc_exit`s), as encoded by
  `pg_noreturn`. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:43`

## Notable internals

- Includes `storage/dsm.h`, `storage/shm_mq.h`, `storage/spin.h` — the minimal
  set for the DSM segment, message queues, and the spinlock in the header. [verified-by-code] `source/src/test/modules/test_shm_mq/test_shm_mq.h:17-19`
- `PGDLLEXPORT` on `test_shm_mq_main` is required for the symbol to be found via
  `bgw_function_name` on platforms where symbols are not exported by default. [from-comment] `source/src/test/modules/test_shm_mq/test_shm_mq.h:43`

## Cross-refs

- `source/src/include/storage/shm_mq.h` — `shm_mq`, `shm_mq_handle`,
  `shm_mq_result`.
- `source/src/include/storage/shm_toc.h` — TOC magic usage.
- `source/src/include/storage/spin.h` — `slock_t`, `SpinLockInit/Acquire/Release`.
- `source/src/include/c.h` — `pg_noreturn`, `PGDLLEXPORT`.

## Potential issues

None.
