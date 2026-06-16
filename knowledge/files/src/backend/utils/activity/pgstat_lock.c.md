# `src/backend/utils/activity/pgstat_lock.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~150
- **Source:** `source/src/backend/utils/activity/pgstat_lock.c`

Implements the lock-statistics flavor of the pgstat shared-memory
counter machinery. Tracks, per locktag type, the number of waits,
total wait time (ms), and the count of fastpath-exceeded events. Kept
in its own file (separate from `pgstat.c`) to enforce the boundary
between generic stats infra and the per-kind accumulator details.
[from-comment] [verified-by-code]

## API / entry points

- `pgstat_count_lock_waits(uint8 locktag_type, long msecs)` —
  increment the per-type wait count and add the elapsed wait time.
  Comment notes: "should not be called in performance-sensitive
  paths" (called when a lock genuinely waited, not on every
  acquisition). [verified-by-code] [from-comment]
- `pgstat_count_lock_fastpath_exceeded(uint8 locktag_type)` —
  increment when a backend wanted a fast-path lock slot but the
  per-backend slot table was full (FP_LOCK_SLOTS_PER_BACKEND
  exhausted). Same performance caveat. [verified-by-code]
  [from-comment]
- `pgstat_lock_flush(bool nowait)` — wrapper for
  `pgstat_lock_flush_cb`. [verified-by-code]
- `pgstat_lock_flush_cb(bool nowait)` — registered callback that
  merges the per-backend `PendingLockStats` into the shared
  `PgStatShared_Lock` under an LWLock, then zeros the pending block.
  Returns true if `nowait` was set and the lock could not be
  acquired (so caller knows to retry). [verified-by-code]
- `pgstat_lock_init_shmem_cb(void *stats)` — shmem init callback,
  initialises the per-tranche LWLock. [verified-by-code]
- `pgstat_lock_reset_all_cb(TimestampTz ts)` — clear the shared
  array and record the reset timestamp. [verified-by-code]
- `pgstat_lock_snapshot_cb(void)` — copy shared into
  `pgStatLocal.snapshot.lock` under SHARED lock. [verified-by-code]
- `pgstat_fetch_stat_lock(void)` — public reader: ensures snapshot
  freshness then returns the snapshot. [verified-by-code]

## Notable invariants / details

- **`PendingLockStats` is process-local** (file-scope `static`).
  Each backend accumulates into its own block, then flushes during
  `pgstat_report_stat` cycles. [verified-by-code]
- **`have_lockstats` short-circuit:** `flush_cb` returns false
  immediately if nothing was recorded — avoids taking the LWLock
  in the common case. Set true by either `count_lock_waits` or
  `count_lock_fastpath_exceeded`. [verified-by-code]
- **`pgstat_report_fixed = true`** is set on every increment so the
  generic pgstat machinery knows the "fixed" (single-instance)
  stats need pushing. This is global module state coordinating with
  pgstat.c. [verified-by-code] [ISSUE-undocumented-invariant: side
  effect on `pgstat_report_fixed` is implicit cross-module coupling
  (nit)]
- **LOCKTAG_LAST_TYPE bound** is asserted on every increment. If
  callers ever pass an out-of-range type the Assert fires in debug,
  and in release builds the write overruns. [verified-by-code]
  [ISSUE-undocumented-invariant: release-build trust in
  LOCKTAG_LAST_TYPE bound (nit)]
- **Loop in `flush_cb` (line 67-75)** uses a token-pasting macro
  `LOCKSTAT_ACC(fld)` to accumulate three fields per locktag. The
  loop iterates `i <= LOCKTAG_LAST_TYPE` (inclusive), matching the
  array sizing convention. [verified-by-code]
- **`nowait` semantics inversion:** `flush_cb` returns true when
  `nowait` was set AND the lock could not be acquired. That's the
  "please retry" signal, not the "success" signal. [verified-by-code]
- **Per-tranche LWLock** `LWTRANCHE_PGSTATS_DATA` is shared with
  other pgstat kinds (per `pgstat_*.c` files). Not a unique tranche
  for lock stats. [verified-by-code]

## Potential issues

- File-line: pgstat_lock.c:130-133, 145-148. The `Assert` on
  `locktag_type <= LOCKTAG_LAST_TYPE` is the only bounds check —
  release builds will write out of bounds if a bad type is passed.
  Existing call sites in `lock.c` are trusted, but a new pgstat
  hook chain could regress this. [ISSUE-correctness: release-build
  bounds check missing on locktag_type (nit)]
- File-line: pgstat_lock.c:147. `(PgStat_Counter) msecs` cast — if
  `msecs` is negative (shouldn't be) we silently get a huge unsigned-ish
  accumulator on platforms where `PgStat_Counter` is unsigned.
  In practice `long` is signed and PgStat_Counter is int64, so the
  cast is benign, but worth a clamp. [ISSUE-style: no clamp on
  negative `msecs` input (nit)]
- File-line: pgstat_lock.c:78-82. `memset(&PendingLockStats, 0, ...)`
  clears state but **does not** reset `pgstat_report_fixed` —
  fine because that flag is owned globally and other kinds may
  still want flushing. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->
