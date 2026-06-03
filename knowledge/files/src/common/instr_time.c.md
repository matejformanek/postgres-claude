# src/common/instr_time.c

## Purpose
Non-inline portion of PG's portable high-precision interval-timing layer.
Sets up the global ticks-per-nanosecond scaling factor used by the
inline `INSTR_TIME_*` macros (in `src/include/portability/instr_time.h`).
Supports two clock sources:

- **System clock** — `clock_gettime(CLOCK_MONOTONIC)` on Unix,
  `QueryPerformanceCounter` on Windows.
- **TSC** (x86-64 RDTSCP) — invariant-TSC fast path, when available and
  the user opts in (or the platform looks reliable).

## Role in PG
Powers `pg_stat_statements`, `EXPLAIN ANALYZE` timing, `track_io_timing`,
`auto_explain` durations, `pgbench` latencies, replication-lag accounting,
and anywhere else PG wants sub-microsecond intervals. Initialized once by
`pg_initialize_timing()` during postmaster start (and by each pgbench
process).

## Key functions
- `pg_initialize_timing(void)` (`instr_time.c:84`) — call once before any
  `INSTR_*` macro. Idempotent. Sets `timing_initialized`.
- `pg_set_timing_clock_source(source)` (`instr_time.c:94`) — choose AUTO /
  SYSTEM / TSC. Returns false if TSC explicitly requested but unusable.
- `set_ticks_per_ns_system` (`instr_time.c:139, 158`) — Unix sets the
  scaler to 0 (clock_gettime already returns nanoseconds, no conversion
  needed); Windows divides 1e9 by `QueryPerformanceFrequency`.
- `pg_initialize_timing_tsc` (`instr_time.c:182`) — runs at most once; if
  TSC frequency is uncached, runs `tsc_detect_frequency`.
- `tsc_detect_frequency` (`instr_time.c:205`) — requires RDTSCP +
  invariant TSC. Tries CPUID first; falls back to a calibration loop
  (`pg_tsc_calibrate_frequency`) that compares TSC against
  `clock_gettime` over up to 50 ms.
- `tsc_use_by_default` (`instr_time.c:276`) — heuristic: trust TSC on
  Intel (TSC_ADJUST feature present) or on Linux where
  `/sys/devices/system/clocksource/clocksource0/current_clocksource`
  reads "tsc" (kernel has already validated it).
- `pg_tsc_calibrate_frequency` (`instr_time.c:318`) — loop up to 1M
  iterations or 50 ms; recomputes frequency each 100 iters; declares
  convergence after 10 consecutive estimates within 0.01%.
- `pg_timing_tsc_clock_source_info` (`instr_time.c:416`) — diagnostic
  accessor; may trigger a lazy calibration.

## State / globals
- `uint64 ticks_per_ns_scaled` (`instr_time.c:61`) — Q-format fixed-point
  ticks→ns multiplier; 0 means "no conversion needed".
- `uint64 max_ticks_no_overflow` (`instr_time.c:62`) — caller-checked
  upper bound for the inline multiplier.
- `bool timing_initialized`, `int timing_clock_source` — init guard.
- `bool timing_tsc_enabled`, `int32 timing_tsc_frequency_khz`
  (`instr_time.c:66-67`) — TSC state.
- `static TscClockSourceInfo tsc_info` (`instr_time.c:73`) — diagnostic
  cache.

## Phase D notes
- **Not user-input touchable.** All inputs to timing setup come from CPU
  feature bits, `/sys` files, or the GUC for clock source — none are
  client-controlled at SQL time.
- **Side-channel surface to clients:** PG exposes nanosecond timings via
  `pg_stat_statements`, EXPLAIN ANALYZE, etc. This *is* a side channel for
  cache-timing attacks (RowHammer-style or branch-predictor
  fingerprinting), but the threat model treats it as accepted — every
  observability tool has the same property.
- **TSC calibration trustworthiness.** The 50 ms cap (`TSC_CALIBRATION_MAX_NS`)
  bounds time spent at startup. The 0.01% convergence threshold is
  generous enough that mild jitter (cron-disturbed clock_gettime) still
  converges. A pathological system could fall back to system clock.
  [verified-by-code: instr_time.c:382-389, 398-399]
- **Overflow path.** Comment at `instr_time.c:50-52` notes overflow only
  matters for intervals > 6.5 days. PG doesn't measure such long
  intervals via `INSTR_TIME_*` (xlog timestamps use TimestampTz). [from-comment]
- **No locking on `tsc_info`.** Only the postmaster touches it during
  init; `pg_timing_tsc_clock_source_info` is meant for diagnostic queries
  in a single backend. Comment at `instr_time.c:411-413` flags that
  EXEC_BACKEND wouldn't see the right info (currently unused in backend).

## Potential issues
- [ISSUE-side-channel: high-precision timings are exposed to clients via
  EXPLAIN ANALYZE and pg_stat_statements. This is the accepted
  observability tradeoff but worth documenting that any attempt to
  "harden" PG against timing-channel CPU attacks would need to dial these
  down. (maybe)]
- [ISSUE-undocumented-invariant: tsc_info struct (instr_time.c:73) is
  not EXEC_BACKEND-safe. Commented at line 411-413. Acceptable today
  because no backend reads it; would silently regress if someone exposed
  pg_timing_tsc_clock_source_info via a SQL function. (low)]
- [ISSUE-stale-todo: comment at line 411 says "*this won't return the
  right info in EXEC_BACKEND builds if this were used in the backend
  (which it currently is not)*" — a TODO masquerading as a comment.
  (low)]
