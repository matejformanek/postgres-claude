# `src/backend/storage/buffer/freelist.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~770
- **Source:** `source/src/backend/storage/buffer/freelist.c`

Owns the buffer-pool replacement strategy: the global clock-sweep
victim selector (`StrategyGetBuffer` / `ClockSweepTick`), the
`BufferAccessStrategy` ring object used by sequential/bulk paths
(BAS_BULKREAD, BAS_BULKWRITE, BAS_VACUUM), and the bgwriter wakeup
plumbing. Despite the historical name, there is no actual "freelist" —
buffers are recycled in-place via the clock sweep. [verified-by-code]

## API / entry points

### Clock sweep / global selection
- `StrategyGetBuffer(strategy, *buf_state, *from_ring)` — main entry
  called by `GetVictimBuffer` (bufmgr.c). If a non-NULL strategy ring
  has a usable slot, return that. Otherwise, walk the clock hand
  via `ClockSweepTick`, CAS-pin the first un-pinned/zero-usagecount
  buffer, decrementing usagecount along the way. Errors with
  `"no unpinned buffers available"` after `NBuffers` consecutive
  pinned-or-CAS-fail iterations (lines 240-316). [verified-by-code]
- `ClockSweepTick(void)` (static inline) — atomically advance
  `nextVictimBuffer` (a `pg_atomic_uint32`); on wraparound take the
  `buffer_strategy_lock` spinlock and `compare_exchange` the counter
  back into `[0, NBuffers)`, incrementing `completePasses`
  (lines 109-166). [verified-by-code]
- `StrategySyncStart(*complete_passes, *num_buf_alloc)` — called by
  bgbufferwriter to read the current clock hand + count of allocations
  since last call (resets the counter). Holds the spinlock to read both
  `completePasses` and `nextVictimBuffer` atomically (lines 330-357).
  [verified-by-code]
- `StrategyNotifyBgWriter(bgwprocno)` — bgwriter registers/clears its
  PGPROC number so the next `StrategyGetBuffer` will set its latch
  (waking it from hibernation). Spinlock-protected store
  (lines 367-378). [verified-by-code]

### Access strategy ring lifecycle
- `GetAccessStrategy(btype)` — pick a default ring size for the given
  bulk-IO type (BAS_BULKREAD scales with `GetPinLimit()` + `io_combine_limit
  * effective_io_concurrency`; BAS_BULKWRITE = 16 MB; BAS_VACUUM = 2 MB)
  and call `GetAccessStrategyWithSize`. BAS_NORMAL returns NULL —
  "default" callers use the global clock sweep (lines 425-501).
  [verified-by-code]
- `GetAccessStrategyWithSize(btype, ring_size_kb)` — palloc the
  `BufferAccessStrategyData` flexarray of `ring_buffers` Buffers; cap
  to `NBuffers / 8` so a strategy can never starve the global pool
  (lines 510-541). [verified-by-code]
- `GetAccessStrategyBufferCount(strategy)`, `GetAccessStrategyPinLimit
  (strategy)` — getters used by callers doing lookahead/prefetch. Pin
  limit for BAS_BULKREAD is the full ring (cheap to give back via
  `StrategyRejectBuffer`); for everything else it's `nbuffers / 2`
  (lines 550-599). [verified-by-code]
- `FreeAccessStrategy(strategy)` — `pfree` (NULL-tolerant for
  "default" strategy callers) (lines 607-613). [verified-by-code]

### Ring internals
- `GetBufferFromRing(strategy, *buf_state)` (static) — advance ring
  cursor, then try to re-pin the buffer that occupied that slot. CAS
  loop returns the buffer if `refcount == 0 && usagecount <= 1`; on
  any other state returns NULL so the caller falls back to clock sweep.
  The `usagecount > 1` check (line 664-665) is how a buffer "escapes"
  the ring when something else touched it. [verified-by-code]
- `AddBufferToRing(strategy, buf)` (static) — records the just-allocated
  buffer into the ring's current slot. Called from `StrategyGetBuffer`
  after a clock-sweep pin succeeded (line 307). Caller must hold the
  buffer-header spinlock at this point per comment at line 698-699.
  [from-comment]
- `IOContextForStrategy(strategy)` — map strategy type to IOContext for
  pgstat (BAS_BULKREAD → IOCONTEXT_BULKREAD, etc.). BAS_NORMAL hits a
  `pg_unreachable()` because GetAccessStrategy returns NULL for it
  (lines 712-738). [verified-by-code]
- `StrategyRejectBuffer(strategy, buf, from_ring)` — called by bufmgr
  when the picked ring buffer is dirty and writing it would force a WAL
  flush. For BAS_BULKREAD only, clear the ring slot and return true
  (ask for a new victim). For other types return false (write and
  reuse). Necessary to prevent infinite loop when every ring slot is
  dirty (lines 751-770). [verified-by-code]

## Notable invariants / details

- `nextVictimBuffer` is a *monotonically increasing* `uint32`, never
  reset; consumers use `% NBuffers` to get the actual buffer index
  (lines 36-42). The wraparound block in `ClockSweepTick` is the *only*
  place that decrements it (via CAS back to wrapped value). The
  comment at lines 145-151 acknowledges that delaying the wrap could
  in theory overflow but says "highly unlikely and wouldn't be
  particularly harmful" — because `% NBuffers` covers the math.
  [from-comment]
- `completePasses` is incremented only inside the wraparound spinlock,
  so `StrategySyncStart` reads it consistently with `nextVictimBuffer`
  to compute the effective high-order bits (line 348). [verified-by-code]
- `numBufferAllocs` counts clock-sweep allocations only — buffers
  recycled via a ring strategy are intentionally not counted (comment
  at lines 232-235). bgwriter sees ring traffic via separate mechanisms.
  [from-comment]
- `bgwprocno = -1` means "no bgwriter to wake"; the `INT_ACCESS_ONCE`
  macro at line 26 forces a single volatile read so the compiler can't
  re-read across the latch-set. Comment at lines 209-216 explicitly
  accepts that "we can set the latch of the wrong process" in a race
  with bgwriter exit — harmless because `procLatch` is never freed.
  [from-comment]
- BAS_BULKREAD ring sizing (lines 442-486): base 256 KB +
  `BLCKSZ * io_combine_limit * effective_io_concurrency` for in-flight
  AIO, capped to `GetPinLimit() * BLCKSZ`. The minimum exists to keep
  `SYNC_SCAN_REPORT_INTERVAL` working (cross-reference at lines 433-434
  points at `access/heap/syncscan.c`). [from-comment]
- BAS_BULKWRITE = 16 MB and BAS_VACUUM = 2 MB are hard-coded (lines
  488-492). [verified-by-code]
- Ring buffer can never exceed `NBuffers / 8` (line 526). The Assert at
  529 says "NBuffers should never be less than 16" so this floor is
  effectively `≥ 2`. [verified-by-code]
- `StrategyRejectBuffer` only fires for BAS_BULKREAD (line 754-755):
  for bulk *write* paths, we actually want to write our own dirty
  buffers — that's the point of buffering them. For vacuum, it
  similarly issues writes. [from-comment]
- The CAS loop in `StrategyGetBuffer` (lines 253-315) handles three
  states per spin: refcount > 0 (skip, decrement `trycounter`), buffer
  header locked (`BM_LOCKED`, wait via `WaitBufHdrUnlocked`),
  usagecount > 0 (decrement and continue), usagecount == 0 (CAS-pin and
  return). The `trycounter` resets to `NBuffers` on a successful
  usagecount decrement (line 293) — so it can only count down all the
  way if every buffer is *pinned* (the ERROR condition), not merely hot.
  [verified-by-code]

## Potential issues

- Line 274. `elog(ERROR, "no unpinned buffers available")` is the
  classic out-of-buffers symptom that surfaces when a leaking backend
  holds excessive pins. The error message says nothing about how to
  diagnose; users see this and have no actionable hint. (`pg_buffercache`
  is the diagnostic, but isn't named in the message.) [ISSUE-doc-drift:
  unhelpful errmsg for buffer exhaustion — no errhint pointing at
  pg_buffercache or shared_buffers (nit)]
- Lines 213-216. The "we can set the latch of the wrong process" race
  with bgwriter exit is acknowledged. Worst case: a few stalled
  allocations until the next clock-sweep allocation tries again. Real
  but bounded. [verified-by-code]
- Line 348. `*complete_passes += nextVictimBuffer / NBuffers` adds the
  number of wraparounds *not yet folded into* `completePasses`. The
  comment "Additionally add the number of wraparounds that happened
  before completePasses could be incremented" is correct but the math
  is subtle: `nextVictimBuffer` can grow arbitrarily before
  `ClockSweepTick` takes the spinlock to fold it. Once folded, the
  high bits are in `completePasses` and `% NBuffers` gives the low
  bits. The current implementation re-reads `nextVictimBuffer` after
  taking the lock (line 337), which is consistent. Cosmetic. [verified-by-code]
- Lines 209-216, 229. `SetLatch(&GetPGProcByNumber(bgwprocno)->procLatch)`
  without ProcArrayLock: the chain of reasoning (procLatch never freed,
  worst case is wrong latch) is sound. Worth flagging because if PG
  ever moves to a model where procLatches *can* be invalidated, this
  becomes a UAF. [ISSUE-undocumented-invariant: bgwriter wakeup assumes
  PGPROC->procLatch is never freed (maybe)]
- Line 467. `ring_max_kb = Max(ring_size_kb, ring_max_kb);` looks like
  a min-floor, not a max-cap — it ensures the cap is *at least* the
  starting size of 256 KB, so the subsequent `if (ring_size_kb > ring_max_kb)`
  (line 483) can never reduce below 256 KB. Logically correct but the
  variable name `ring_max_kb` is misleading after this assignment.
  [ISSUE-style: variable named `ring_max_kb` actually carries the cap
  AFTER a min-floor; confusing (nit)]
- Line 528. `Assert(ring_buffers > 0)` — comment says "NBuffers should
  never be less than 16, so this shouldn't happen", but if a future
  change reduces `MinBuffers` below 8, the Assert would fire silently
  in release builds (it's an Assert, not ereport). Cosmetic — guarded
  by another Assert elsewhere. [verified-by-code]
- Line 738. `pg_unreachable()` after `elog(ERROR, ...)` is redundant
  belt-and-suspenders. Cosmetic. [verified-by-code]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new BufferAccessStrategy ring](../../../../../scenarios/add-new-buffer-strategy.md)
- [Scenario — Add a new BufferAccessStrategy ring](../../../../../scenarios/add-new-buffer-strategy.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `storage-buffer`](../../../../../issues/storage-buffer.md)
<!-- issues:auto:end -->
