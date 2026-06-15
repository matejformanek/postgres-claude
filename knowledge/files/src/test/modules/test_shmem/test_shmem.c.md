# src/test/modules/test_shmem/test_shmem.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 101
**Verification depth:** full read

## Role

Test module exercising the named shared-memory allocation API via the `ShmemCallbacks` registration mechanism. Its distinguishing feature versus other modules is exercising allocation of (non-DSM) shared memory *after* postmaster startup, signalled by `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP`. [from-comment] `source/src/test/modules/test_shmem/test_shmem.c:6-8`. It registers request/init/attach callbacks that allocate a small `TestShmemData` struct and track an attach count, with a SQL function to read that count back. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:42-47,89,92-100`

## Public API

- `_PG_init(void)` — registers the shmem callbacks via `RegisterShmemCallbacks(&TestShmemCallbacks)`. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:85-90`
- `get_test_shmem_attach_count(PG_FUNCTION_ARGS)` — SQL-callable; returns `TestShmem->attach_count`, erroring if the current process never attached/initialized or the area is uninitialized. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:92-100`
- `TestShmemCallbacks` — static `ShmemCallbacks` with `.flags = SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` and request/init/attach function pointers. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:42-47`

## Invariants

- INV-1: `test_shmem_request` calls `ShmemRequestStruct` with name `"test_shmem area"`, size `sizeof(TestShmemData)`, binding the result pointer into the static `TestShmem`. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:49-57`
- INV-2: The init callback runs exactly once per area (guarded by `TestShmem->initialized`); a second init is an error. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:62-65`
- INV-3: Within a single process, exactly one of init or attach runs — enforced by the process-local `attached_or_initialized` flag; either callback firing twice in one process is an error. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:36,67-69,80-82`
- INV-4: The attach callback requires the area to already be initialized (`TestShmem->initialized`), else error. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:76-77`

## Notable internals

- `TestShmemData` carries `value`, `initialized`, `attach_count`; `attach_count` is bumped by every attaching process. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:27-32,78`
- The module distinguishes "initialize" (the creating process) from "attach" (other processes mapping the existing area) — only one path per process. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:59-83`
- All callbacks emit `elog(LOG, ...)` markers, which the TAP test asserts against. [verified-by-code] `source/src/test/modules/test_shmem/test_shmem.c:52,62,75,88`

## Cross-refs

- `source/src/include/storage/shmem.h` — ShmemCallbacks, RegisterShmemCallbacks, ShmemRequestStruct, SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP.
- `source/src/backend/storage/ipc/shmem.c` — named shmem allocation backend.
- `source/src/backend/storage/ipc/ipci.c` — shmem startup orchestration.
- `source/src/test/modules/test_shmem/t/001_basic.pl` — TAP test driving the callbacks.

## Potential issues

None.
