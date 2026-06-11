# `src/bin/pg_test_timing/pg_test_timing.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~457
- **Source:** `source/src/bin/pg_test_timing/pg_test_timing.c`

Microbenchmark of the platform's clock source(s). For a configurable
duration (default 3 s), tight-loops `INSTR_TIME_SET_CURRENT`, recording
the distribution of consecutive-sample differences in two histograms
(power-of-2 buckets + direct ns buckets up to 10000), and detecting clock
regressions. On x86 / supported architectures also tests the TSC clock
source (both "slow" RDTSCP and "fast" RDTSC variants) and warns if the
calibrated TSC frequency drifts more than 10 % from the in-use value.
[verified-by-code] [from-comment]

## API / entry points

- `main` — `handle_args`, `pg_initialize_timing` (required for
  INSTR_* calls), `test_system_timing`, then (on x86) `test_tsc_timing`.
  [verified-by-code]
- `handle_args` — parses `-d / --duration` (seconds, >0) and `-c /
  --cutoff` (percentage cutoff for direct histogram output, default
  99.99). [verified-by-code]
- `test_timing(duration, source, fast_timing)` — the inner loop.
  Selects the requested clock source via `pg_set_timing_clock_source`
  (may fail → return 0 → "not usable"), zero-touches the histograms,
  then loops calling `INSTR_TIME_SET_CURRENT(_FAST)` and recording
  the diff. Detects negative diffs as "Detected clock going backwards"
  and exits 1 immediately. [verified-by-code]
- `test_system_timing` — wrapper around `test_timing` with
  `TIMING_CLOCK_SOURCE_SYSTEM`. Always emits output because the system
  clock is always available. [verified-by-code]
- `test_tsc_timing` (x86 only) — slow RDTSCP first, then RDTSC, then
  prints `TscClockSourceInfo` (frequency source, frequency in kHz,
  calibrated frequency, ±%). Warns and exits 1 if calibration differs
  >10%. Probes whether the AUTO selection would pick TSC by default.
  [verified-by-code]
- `output(loop_count)` — formats two histograms: power-of-2 buckets
  for "<= ns" (every observed diff) and direct ns buckets for percentile
  reporting (printing rows until cumulative reaches `max_rprct`, then
  always including the largest observed diff if it's still in the direct
  range). [verified-by-code]

## Notable invariants / details

- The power-of-2 histogram is sized 64 entries (`histogram[64]`).
  `pg_leftmost_one_pos64(diff) + 1` is asserted < 64 (line 322); won't
  trip in practice. [verified-by-code]
- The direct histogram is sized `NUM_DIRECT = 10000` ns; anything beyond
  is folded into `largest_diff` + `largest_diff_count`. [verified-by-code]
- Memset-then-touch of `direct_histogram` and `histogram` (lines 281-282)
  is deliberately done to bring the pages into the working set (avoid
  COW glitches mid-measurement). [from-comment]
- On TSC failure (`loop_count == 0` from `test_tsc_timing`), the report
  still includes the frequency-source info because it's helpful for bug
  reports. [from-comment]
- `pg_set_timing_clock_source(TIMING_CLOCK_SOURCE_AUTO)` is called near
  the end of `test_tsc_timing` to mirror whatever the runtime auto-pick
  would produce; the choice between "by default" / "not by default"
  messages comes from comparing `pg_current_timing_clock_source()`
  against TSC. [verified-by-code]
- Cutoff `-c` is a double clipped to [0, 100]. [verified-by-code]

## Potential issues

- `pg_test_timing.c:309-315` — negative diff exits 1 immediately,
  losing any partial histogram data. Single-event clock regressions
  (NTP slew under load) thus require multiple runs to characterize.
  [ISSUE-correctness: even a single backwards step aborts the run
  (nit)]
- `pg_test_timing.c:221-226` — TSC frequency disagreement >10% exits 1
  AFTER printing the diff-pct line; that means a benchmark used by ops
  staff to *diagnose* drift refuses to print the histogram once drift
  is confirmed. Arguably surprising. [ISSUE-style: exit-on-drift fights
  the diagnostic use case (nit)]
- `pg_test_timing.c:402-407` — uses `%lld` and `%llu` formatters on
  `long long` casts. The casts at line 403 and line 452 use `(long long)
  largest_diff` but lines 402, 451 use `%llu` and rely on `1ULL <<` and
  `histogram[i]` being `long long int`. Consistent on standard ILP64
  platforms but a `PRId64` style would be cleaner.
  [ISSUE-style: mixed %lld and PRI macros (nit)]
- `pg_test_timing.c:154-157` — `printf(ngettext("%u second per test"...
  test_duration))` — `ngettext` matches the singular `1` only;
  any other duration uses plural, which is what we want. [verified-by-code]
- `pg_test_timing.c:118` — `errno = 0; max_rprct = strtod(optarg,
  &endptr);` — strtod's errno reporting is platform-flaky for overflow
  to infinity. The range check at 128 catches negatives and >100 but a
  parsed Inf passes through 0..100 range trivially. Wait, Inf > 100 so
  is caught. [verified-by-code]
- The histogram-bottom row `(1ULL << 0) - 1 = 0` is labelled "<= 0 ns"
  in the header (line 391-392); fine but worth noting that the bucket
  semantics mean "less than 2^i ns" so the smallest bucket is "0 ns".
  [verified-by-code]
