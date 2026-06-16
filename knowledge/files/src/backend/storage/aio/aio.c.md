---
path: src/backend/storage/aio/aio.c
anchor_sha: 4b0bf0788b0
loc: 1358
depth: deep
---

# aio.c

- **Source path:** `source/src/backend/storage/aio/aio.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1358

## Purpose

**The core logic of the PG18 AIO subsystem** — handle acquisition,
the state-machine transitions, the generation/wait-reference machinery,
reclaim/reuse, batch submission, and the error/transaction/shutdown
cleanup hooks. Everything method-specific lives in `method_*.c`; this
file is "all other topics" per its own file header (aio.c:6-27). The
`io_method` and `io_max_concurrency` GUC variables and the
method-dispatch table (`pgaio_method_ops_table`) live here.
[from-comment, aio.c:1-37]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_io_acquire(resowner, ret)` | `aio.c:161` | acquire a handle, **block** if none free |
| `pgaio_io_acquire_nb(resowner, ret)` | `aio.c:187` | acquire or return NULL |
| `pgaio_io_release(ioh)` | `aio.c:239` | give back an un-needed handed-out handle |
| `pgaio_io_release_resowner(node, on_error)` | `aio.c:265` | resowner-cleanup release path |
| `pgaio_io_set_flag(ioh, flag)` | `aio.c:329` | OR a `PgAioHandleFlags` in |
| `pgaio_io_get_id(ioh)` | `aio.c:341` | index of handle in global array |
| `pgaio_io_get_owner(ioh)` | `aio.c:354` | owning `ProcNumber` |
| `pgaio_io_get_wref(ioh, iow)` | `aio.c:365` | snapshot a wait reference (incl. generation) |
| `pgaio_io_stage(ioh, op)` | `aio.c:423` | DEFINED→STAGED(→submit/sync); called by `pgaio_io_start_*` |
| `pgaio_io_needs_synchronous_execution(ioh)` | `aio.c:482` | hint + method query |
| `pgaio_io_prepare_submit(ioh)` | `aio.c:509` | STAGED→SUBMITTED, push to in-flight |
| `pgaio_io_process_completion(ioh, result)` | `aio.c:527` | SUBMITTED→COMPLETED_IO→COMPLETED_SHARED + CV broadcast |
| `pgaio_io_was_recycled(ioh, gen, *state)` | `aio.c:558` | generation check w/ read barrier |
| `pgaio_wref_clear/_valid/_get_id` | `aio.c:963,970,979` | wait-ref helpers |
| `pgaio_wref_wait(iow)` | `aio.c:990` | block until referenced IO completes (any process) |
| `pgaio_wref_check_done(iow)` | `aio.c:1004` | non-blocking completion poll |
| `pgaio_enter_batchmode/_exit_batchmode` | `aio.c:1090,1101` | batch-submission control |
| `pgaio_have_staged/_submit_staged` | `aio.c:1116,1132` | staged-IO inspection / flush |
| `pgaio_closing_fd(fd)` | `aio.c:1229` | submit + (if needed) drain IOs using an FD |
| `pgaio_error_cleanup` / `AtEOXact_Aio` / `pgaio_shutdown` | `aio.c:1174,1202,1297` | cleanup hooks |
| `assign_io_method` / `check_io_max_concurrency` | `aio.c:1331,1340` | GUC hooks |

## Internal landmarks

- **`pgaio_io_update_state` (aio.c:385)** — the *only* legal way to
  change `ioh->state`. Asserts interrupts are held off, issues a
  `pg_write_barrier()` so the field changes implied by the new state
  are visible before the state itself.
- **`pgaio_io_reclaim` (aio.c:674)** — the reuse path: runs
  `complete_local` callbacks (if still COMPLETED_SHARED), fills
  `report_return`, bumps `generation`, resets the handle to IDLE, and
  pushes it to the *head* of `idle_ios` (cache-friendly). State+gen are
  updated *before* the fields are reset, with a write barrier between,
  so a concurrent viewer never sees a half-reset "live" handle.
- **`pgaio_io_wait` (aio.c:578)** — the central wait loop, generation-
  guarded; in SUBMITTED state it defers to the method's `wait_one()`
  unless the issuer is doing the IO synchronously, otherwise sleeps on
  the handle CV.
- **`pgaio_io_wait_for_free` (aio.c:760)** — backs `pgaio_io_acquire`'s
  blocking: first reclaims any of *our* COMPLETED_SHARED handles, then
  submits staged IOs, then waits for the oldest in-flight IO.
- **`pgaio_method_ops_table[]` (aio.c:84)** — designated-initializer
  dispatch table indexed by `IoMethod`; a `StaticAssertDecl`
  (aio.c:92) keeps it in sync with `io_method_options[]`.

## Invariants & gotchas

- **At most one handle may be HANDED_OUT per backend** —
  `pgaio_io_acquire_nb` `elog(ERROR)`s on a second hand-out
  (aio.c:198-199). This is the core deadlock-avoidance rule: it
  guarantees a backend can always wait for an in-flight IO to free a
  handle. `pgaio_io_stage` clears `handed_out_io` as soon as the IO is
  defined (aio.c:445), allowing the next acquire.
- **All state transitions hold interrupts off.**
  `pgaio_io_update_state` asserts `!INTERRUPTS_CAN_BE_PROCESSED()`
  (aio.c:393). Acquire/stage/release/reclaim all wrap their work in
  `HOLD_INTERRUPTS()`/`RESUME_INTERRUPTS()` because an interrupt could
  otherwise try to wait for an IO mid-transition and corrupt state.
- **Completion runs in a critical section.**
  `pgaio_io_process_completion` asserts `CritSectionCount > 0`
  (aio.c:532) — IOs must be completable inside critical sections
  (e.g. WAL flush), so the whole completion path, including
  `complete_shared` callbacks, must be no-throw. Failure is signaled by
  the result, never by ereport.
- **Generation, not pointer, gates waiting.** `pgaio_io_get_wref`
  asserts `generation != 0` (aio.c:371; init sets generation=1 in
  `aio_init.c`). A wait reference is `{index, generation}`; once the
  handle is reused its generation moves on and any waiter on the old
  generation correctly concludes "already done."
- **`pgaio_submit_staged` wraps the method `submit` in a critical
  section** (aio.c:1142-1147) — consistent with completion-in-critsec.
- **Batchmode is a deadlock footgun.** While staged-but-unsubmitted IOs
  exist, the issuer must not block waiting on another backend, or two
  backends can each wait on the other's unsubmitted IO forever
  (aio.c:1060-1088). Callers opt in explicitly and must use conditional
  lock acquisition / `pgaio_have_staged` / `pgaio_submit_staged`.
- **`pgaio_closing_fd` must run before any FD close** (aio.c:1229) —
  staged IOs reference raw FDs, so they're force-submitted before the
  FD goes away; if the method sets `wait_on_fd_before_close` (io_uring),
  in-flight IOs using that FD are also drained.
- **An empty in-flight list with no free handle is a hard error**
  (aio.c:812-818) — "no free IOs despite no in-flight IOs" would mean a
  handle leak.

## Cross-refs

- Structs + state machine: `knowledge/files/src/include/storage/aio_internal.h.md`.
- Public interface: `knowledge/files/src/include/storage/aio.h.md`.
- Callbacks invoked from completion: `aio_callback.c.md`.
- Methods: `method_worker.c.md`, `method_io_uring.c.md`, `method_sync.c.md`.
- Subsystem entry points: `knowledge/files/src/include/storage/aio_subsys.h.md`.
- Interrupt/critical-section idiom: `knowledge/idioms/error-handling.md`.

<!-- issues:auto:begin -->
- [Issue register — `storage-aio`](../../../../../issues/storage-aio.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: `report_return` lifetime tied to
  resowner, cleared on early release]** `aio.c:316-317, 156-159` — the
  caller's `PgAioReturn *` must outlive the resowner; on resowner
  cleanup the pointer is nulled and the IO result is silently *not*
  reported. Callers that stash `PgAioReturn` in a longer-lived context
  than `CurrentResourceOwner` get no completion info on error paths.
  Severity: maybe.
- **[ISSUE-question: `pgaio_io_wait_for_free` waits for a *specific*
  oldest IO, not *any* IO]** `aio.c:822-824` — the `XXX` admits reusing
  the general wait is "suboptimal": we only need *any* IO to complete,
  but we block on the head of the in-flight list. Under io_uring where
  another backend may complete a later IO first, this can wait longer
  than necessary. Severity: nit (author-acknowledged).

## Tally

`[verified-by-code]=8 [from-comment]=5 [inferred]=1`
