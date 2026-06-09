# 2026-06-08 — cloud/pg-file-backfiller: PG18 AIO subsystem + rmgrdesc sweep

**Routine:** `pg-file-backfiller` (daily cloud). **Branch:**
`cloud/pg-file-backfiller/2026-06-08`. **Anchor:** `4b0bf0788b06`.

## What happened

The queue head (`src/backend/libpq`, 17 `.c`) was **stale on refill** — all
17 already deep-covered by the A2 sweep (2026-06-03, PR #41). `coverage-gaps.md`
had carried a contradictory "libpq 17 | 0 | 0.0%" row, and the 2026-06-07
timezone run copied that into the queue without checking the `.c` directory.
Audited + closed the block (`[done:covered-2026-06-03]`), recomputed the
genuine gap from the GitHub tree API at anchor (**1 127 uncovered .c/.h**),
and popped two coherent high-value clusters.

## Cluster 1 — `src/backend/storage/aio` (PG18 AIO subsystem), 14 docs

Complete-the-directory: 10 `.c` + 4 `src/include/storage/aio*.h`. STATE.md's
**top `knowledge/subsystems/storage-aio.md` candidate** (AIO/read-stream/
io_uring demand-signalled 4× by pg-user-question-harvester #71).

Headlines captured in the docs:

- **Handle state machine** (`aio_internal.h`): 8 states
  IDLE→HANDED_OUT→DEFINED→STAGED→SUBMITTED→COMPLETED_IO→COMPLETED_SHARED→
  COMPLETED_LOCAL, all transitions via `pgaio_io_update_state` with
  write-barriers; generation bump on reuse is what makes cross-process
  `PgAioWaitRef`s safe.
- **The one-handed-out-handle rule** (`aio.c`) is the core deadlock-avoidance
  invariant: a backend may hold at most one un-defined handle so it can
  always wait for an in-flight IO to free one. Completion runs **in a
  critical section** (asserts `CritSectionCount > 0`) and may run in *another*
  backend → callbacks can never ereport; errors are deferred to the issuer
  via `PgAioReturn`/`pgaio_result_report`.
- **Worker is the default `io_method`**, not io_uring (io_uring is Linux-only,
  opt-in, `EXEC_BACKEND`-incompatible). Worker mode: shared submission ring +
  uint64 worker bitmap, elastic pool (`io_min/max_workers`), wakeup-
  propagation "frontier" heuristic, full-queue→synchronous-in-issuer fallback.
- **io_uring**: one ring per backend created in postmaster (so any backend can
  drain a blocked issuer's completions under `completion_lock`); submit-EAGAIN
  → PANIC by design; `IOSQE_ASYNC` heuristic for buffered IO.
- **read_stream.c** — the most-asked-about file: adaptive *combine* +
  *readahead* distances (double on wait, decay on hit with a holdoff), a
  fast path for all-cached scans, forwarded-buffer accounting, an int16
  ~32k-pinned-buffer geometry cap. Synchronous IO is *treated as a wait* so
  combining still ramps at `effective_io_concurrency=0`.

New register `knowledge/issues/storage-aio.md` (11 issues, mostly
author-acknowledged design trade-offs). Notable: `pg_aios` exposes
cross-backend IO target/offset metadata (info-disclosure); worker single-queue
scaling ceiling; io_uring EAGAIN→PANIC cluster-crash amplifier.

## Cluster 2 — `src/backend/access/rmgrdesc` (6 of 22), WAL-format docs

The highest-WAL-format-value descs, complementing the `wal-and-xlog` skill:

- `rmgrdesc_utils.c` — shared `array_desc` + element printers (canonical
  waldump array format).
- `xlogdesc.c` — checkpoint decoder (best in-tree `CheckPoint` field
  reference); `wal_level_options` table; `XLogRecGetBlockRefInfo` (waldump
  FPI accounting + compression method).
- `xactdesc.c` — **canonical `ParseCommit/Abort/PrepareRecord`** shared
  between redo and waldump; the `xinfo`-gated variable-length commit wire
  format; the "no alignment after two-phase, memcpy origin to stack" gotcha.
- `heapdesc.c` — heap/heap2 record set; **`heap_xlog_deserialize_prune_and_
  freeze`** (shared redo+waldump deserializer); infobits + VM-bit decoding.
- `clogdesc.c` — CLOG zeropage/truncate only (status bits aren't individually
  WAL-logged); int64 pageno.
- `standbydesc.c` — hot-standby records + the **shared
  `standby_desc_invalidations`** reused by xact/heap descs.

16 lower-value per-AM descs left `[pending]` in the queue for the next run.

## Ledger / counters

- Per-file docs **+20** (find-based total now **1 555**; the STATE headline
  counter lineage was 1 504 → set to 1 524 — note a ~31-doc drift between the
  headline counter and the on-disk `find` count, flagged for pg-state-keeper
  to reconcile).
- `progress/files-examined.md` +20 rows.
- `progress/coverage-gaps.md`: libpq corrected 0/17→17/17; storage/aio 10/10
  added; "recompute gap from tree" standing note added.

## For next time

- Build `knowledge/subsystems/storage-aio.md` — now well-supported.
- Refill the queue by recomputing the genuine gap from the GitHub tree at the
  anchor; do **not** trust `coverage-gaps.md` per-subdir 0% rows.
