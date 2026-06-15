---
path: src/test/modules/test_shmem/test_shmem.c
anchor_sha: e18b0cb7344
loc: 101
depth: read
---

# src/test/modules/test_shmem/test_shmem.c

## Purpose

Exercises the (non-DSM) shared-memory allocation API for extensions,
specifically the rarely-tested case of allocating shared memory **after
postmaster startup** via `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP`. Verifies the
attach-vs-initialize callback split (init runs once in the postmaster, attach
runs in every child backend), with assertions that each callback runs exactly
once per process. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `test_shmem.c:85` | Registers `TestShmemCallbacks` |
| `get_test_shmem_attach_count` | `:92` | Returns `TestShmem->attach_count` after asserting attach/init ran |
| `test_shmem_request` (static) | `:49` | Calls `ShmemRequestStruct(.name, .size, .ptr=&TestShmem)` |
| `test_shmem_init` (static) | `:59` | Asserts not previously initialized; sets `initialized=true` |
| `test_shmem_attach` (static) | `:72` | Asserts initialized; bumps `attach_count` |

## Internal landmarks

- `TestShmemCallbacks` (`:42`) sets `.flags = SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP`
  — the whole point of this module, since most shmem requests must happen
  during `shared_preload_libraries` processing.
- `attached_or_initialized` is a per-process static (`:36`) that catches the
  "callback ran twice in one process" bug. The init callback runs in the
  postmaster; the attach callback runs in each backend; neither should run
  twice for a given process.

## Invariants & gotchas

- **Test module — never load in production.**
- The `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` flag is what lets this module
  be loaded by `LOAD 'test_shmem'` from a regular SQL session — without the
  flag, post-startup shmem allocation would error out.
- `attach_count` is per-instance across all processes — every new backend
  bumps it by 1, so the regression test can observe forks happening.
- `TestShmem` is a process-private pointer set by the `ShmemRequestStruct`
  call; in each new backend the attach callback resolves it to the same
  shared memory area.

## Cross-refs

- `source/src/backend/storage/ipc/shmem.c` — `ShmemRequestStruct`,
  `RegisterShmemCallbacks`.
- `source/src/include/storage/shmem.h` — the `ShmemCallbacks` struct and
  `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` flag.
