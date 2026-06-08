---
path: src/include/storage/aio_subsys.h
anchor_sha: 4b0bf0788b0
loc: 34
depth: read
---

# aio_subsys.h

- **Source path:** `source/src/include/storage/aio_subsys.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 34

## Purpose

The "**interact with AIO as a subsystem, not as an IO issuer**" header.
For callers like `postmaster.c` and shmem init that must initialize or
poke the AIO subsystem at lifecycle boundaries but never issue an IO
themselves. Keeping these few entry points out of `aio.h` avoids
dragging the full handle interface into those files.
[from-comment, aio_subsys.h:1-9]

## Public symbols

| Symbol | Defined in | Line | Role |
|---|---|---|---|
| `pgaio_init_backend(void)` | `aio_init.c` | `aio_subsys.h:23` | per-backend AIO init (registers `pgaio_shutdown`) |
| `pgaio_error_cleanup(void)` | `aio.c` | `aio_subsys.h:27` | early error-path cleanup (exits batchmode, submits staged IOs) |
| `AtEOXact_Aio(bool is_commit)` | `aio.c` | `aio_subsys.h:28` | (sub-)transaction-boundary sanity check |
| `pgaio_workers_enabled(void)` | `method_worker.c` | `aio_subsys.h:32` | true iff `io_method == IOMETHOD_WORKER` |

## Invariants & gotchas

- **`pgaio_error_cleanup()` must run early in error recovery**
  (aio.c:1168-1193) — later abort steps may themselves need to issue
  AIO (e.g. writing an abort WAL record), so any open batch must be
  closed and staged IOs submitted first.
- **`AtEOXact_Aio` is a late check** (aio.c:1202): it asserts no
  unsubmitted IOs remain at commit/abort and WARNs if a batch was left
  open. It is correctness-tolerant (force-submits) but flags the bug.

## Cross-refs

- Implementations: `knowledge/files/src/backend/storage/aio/aio.c.md`,
  `aio_init.c.md`, `method_worker.c.md`.
- The full IO-issuing interface is `aio.h` (separate header on purpose).

## Tally

`[verified-by-code]=2 [from-comment]=1 [inferred]=0`
