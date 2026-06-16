---
path: src/include/storage/aio_internal.h
anchor_sha: 4b0bf0788b0
loc: 421
depth: deep
---

# aio_internal.h

- **Source path:** `source/src/include/storage/aio_internal.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 421

## Purpose

The AIO subsystem's **private** header — the load-bearing data model:
the `PgAioHandleState` state machine, the full `PgAioHandle` struct,
the per-backend `PgAioBackend` state, the global `PgAioCtl`, the
`IoMethodOps` vtable each IO method implements, and the `pgaio_debug*`
logging macros. Only AIO-internal `.c` files include this.
[from-comment, aio_internal.h:1-13]

## Public symbols (internal-only)

| Symbol | Kind | Line | Notes |
|---|---|---|---|
| `PGAIO_SUBMIT_BATCH_SIZE` | macro | `aio_internal.h:30` | 32 — max IOs batch-submitted at once |
| `PgAioHandleState` | enum | `aio_internal.h:45` | the 8-state handle lifecycle (see below) |
| `PgAioHandle` | struct | `aio_internal.h:104` | the IO handle itself |
| `PgAioBackend` | struct | `aio_internal.h:193` | per-backend: idle/staged/in-flight lists |
| `PgAioCtl` | struct | `aio_internal.h:231` | global: handle array + iovec/handle-data pools |
| `IoMethodOps` | struct | `aio_internal.h:262` | per-method vtable |
| `PGAIO_VERBOSE` | macro | `aio_internal.h:376` | compile-time debug-logging switch (default 1) |
| `pgaio_debug` / `pgaio_debug_io` | macro | `aio_internal.h:387,400` | conditional ereport wrappers |
| `pgaio_sync_ops` / `pgaio_worker_ops` / `pgaio_uring_ops` | extern | `aio_internal.h:409-412` | method vtables |
| `pgaio_ctl`, `pgaio_my_backend`, `pgaio_method_ops` | extern | `aio_internal.h:415-417` | the three globals |

## The handle state machine (`PgAioHandleState`)

Handles move **linearly** through states (with documented exceptions),
all transitions via `pgaio_io_update_state()` (aio.c:385):

```
IDLE → HANDED_OUT → DEFINED → STAGED → SUBMITTED
     → COMPLETED_IO → COMPLETED_SHARED → COMPLETED_LOCAL → (IDLE, reused)
```

- `IDLE` — in the per-backend `idle_ios` list, not in use.
- `HANDED_OUT` — returned by `pgaio_io_acquire()`, not yet defined.
  **At most one handle per backend may be in this state** (enforced by
  `PgAioBackend->handed_out_io`).
- `DEFINED` — `pgaio_io_start_*()` called, IO fully specified.
- `STAGED` — stage callbacks run; ready to submit (sits in
  `staged_ios[]` array until submitted).
- `SUBMITTED` — handed to the IO method; on the issuer's
  `in_flight_ios` list.
- `COMPLETED_IO` — IO finished, result not yet processed.
- `COMPLETED_SHARED` — shared completion callbacks ran. If the issuer
  is the completer, local callbacks run immediately; otherwise the
  handle waits here until the issuer waits for it.
- `COMPLETED_LOCAL` — local callbacks ran; handle about to be reclaimed.

The per-state list membership is documented inline at
aio_internal.h:138-147 and is the map for reading `aio.c`.

## Invariants & gotchas

- **`state`, `target`, `op`, `flags` are `uint8`, not their enums**
  (aio_internal.h:106-116) — deliberately, to save shared-memory
  space; the comment notes bitfields generate "horrid code" on several
  compilers. Always cast back (`(PgAioHandleState) ioh->state`) before
  switching, as the code does throughout.
- **`generation` is incremented on every reuse** (aio_internal.h:153)
  and is what makes a `PgAioWaitRef` safe: a stale reference whose
  generation no longer matches means "the IO you cared about already
  completed and the handle was reused" — see
  `pgaio_io_was_recycled` (aio.c:558).
- **The handle carries its own `ConditionVariable`** (aio_internal.h:161)
  for cross-backend waiting; a waiter in `SUBMITTED` state must first
  ask the IO method's `wait_one()` before sleeping on the CV.
- **`PgAioCtl` allocates iovecs and handle-data in `PgAioCtl`, not in
  the handle** (aio_internal.h:236-254), so the max iovec count per IO
  is a `PGC_POSTMASTER` GUC (`io_max_combine_limit`) rather than a
  compile constant. `iovec_off` indexes both pools.
- **`IoMethodOps` is the method abstraction.** Required:
  `submit`. Optional: `needs_synchronous_execution`, `wait_one`,
  `check_one`, `init_backend`, `shmem_callbacks`. The
  `wait_on_fd_before_close` bool (aio_internal.h:270) is the
  io_uring-specific IOSQE_ASYNC-vs-FD-close hazard flag. `submit` is
  **always called in a critical section** and must advance state to at
  least `SUBMITTED` (aio_internal.h:286-298).
- **`pgaio_debug*` compiles the logging code even when `PGAIO_VERBOSE`
  is 0** (guarded by `if (0)`), so debug logging can't silently
  bit-rot (aio_internal.h:378-394). There's an `XXX` note that it
  should probably default off in non-assert builds — see Potential
  issues.

## Cross-refs

- Public interface: `knowledge/files/src/include/storage/aio.h.md`.
- Types: `knowledge/files/src/include/storage/aio_types.h.md`.
- State transitions live in `aio.c::pgaio_io_update_state` and callers.
- Method vtables: `method_sync.c`, `method_worker.c`, `method_io_uring.c`.
- Locking idiom for the CV + read/write barriers: `knowledge/idioms/locking-overview.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-storage`](../../../../issues/include-storage.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-todo: `PGAIO_VERBOSE` defaults on in production builds]**
  `aio_internal.h:373-376` — the `XXX` says this "likely should be
  eventually be disabled by default, at least in non-assert builds";
  the comment itself notes that even elided logging "causes a
  measurable slowdown" because args are still evaluated. Open
  perf/tunable question. Severity: nit.

## Tally

`[verified-by-code]=4 [from-comment]=5 [inferred]=0`
