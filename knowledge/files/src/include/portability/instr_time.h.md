# `src/include/portability/instr_time.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~465
- **Source:** `source/src/include/portability/instr_time.h`

Portable high-precision interval timing. Defines the opaque
`instr_time` type plus a family of `INSTR_TIME_*` macros that
abstract over `clock_gettime(CLOCK_MONOTONIC[_RAW])` on POSIX,
`QueryPerformanceCounter()` on Windows, and direct RDTSC/RDTSCP on
x86_64 when the `timing_tsc_enabled` GUC path is active. Internally
stores ticks as int64 to keep add/subtract cheap. [from-comment]
[verified-by-code]

## API / declarations

### Type

- `typedef struct instr_time { int64 ticks; } instr_time;` —
  caller-opaque; "users of the API should rely on the integer
  representation" is explicitly NOT supported. [from-comment]

### Operations (macros — beware multi-evaluation)

- `INSTR_TIME_IS_ZERO(t)`, `INSTR_TIME_SET_ZERO(t)`.
- `INSTR_TIME_SET_CURRENT_FAST(t)` — set to NOW without waiting for
  out-of-order instructions to retire.
- `INSTR_TIME_SET_CURRENT(t)` — set to NOW *with* OOO-fence so
  measurements bracket the right instructions.
- `INSTR_TIME_ADD(x, y)` (x+=y), `INSTR_TIME_ADD_NANOSEC(t, n)`.
- `INSTR_TIME_SUBTRACT(x, y)` — converts absolute → interval.
- `INSTR_TIME_ACCUM_DIFF(x, y, z)` — `x += (y - z)` in one step.
- `INSTR_TIME_GT(x, y)` (bool).
- Getters (only meaningful on intervals):
  `INSTR_TIME_GET_DOUBLE(t)` (seconds),
  `INSTR_TIME_GET_MILLISEC(t)` (ms double),
  `INSTR_TIME_GET_MICROSEC(t)` (us int64),
  `INSTR_TIME_GET_NANOSEC(t)` (ns int64). [from-comment]

### Helpers and constants

- `NS_PER_S = 1000000000`, `NS_PER_MS = 1000000`,
  `NS_PER_US = 1000` (all int64).
- `TICKS_TO_NS_SHIFT = 14` — fixed-point shift used by
  `pg_ticks_to_ns`/`pg_ns_to_ticks` when ticks-≠-ns.
- `PG_INSTR_TICKS_TO_NS` — 1 on x86_64 + WIN32, 0 elsewhere. Drives
  whether `pg_ticks_to_ns` does conversion or just returns.
- `PG_INSTR_TSC_CLOCK` — 1 on x86_64, 0 on WIN32 + others.

### Clock-source machinery

- `enum TimingClockSourceType { TIMING_CLOCK_SOURCE_AUTO,
  TIMING_CLOCK_SOURCE_SYSTEM, [TIMING_CLOCK_SOURCE_TSC iff
  PG_INSTR_TSC_CLOCK] }`.
- `pg_initialize_timing(void)` — must be called once before any
  `INSTR_TIME_SET_CURRENT*`.
- `pg_set_timing_clock_source(source)` — bool; intended for
  frontends. Backends should set the `timing_clock_source` GUC.
- `pg_current_timing_clock_source()` — resolves AUTO.
- Runtime state: `ticks_per_ns_scaled`, `max_ticks_no_overflow`,
  `timing_initialized`, `timing_tsc_enabled`,
  `timing_tsc_frequency_khz` (-1 = uninit, 0 = TSC unusable,
  >0 = kHz).
- `TscClockSourceInfo { frequency_khz, calibrated_frequency_khz,
  frequency_source[128] }` + `pg_timing_tsc_clock_source_info()`.
- `PG_INSTR_SYSTEM_CLOCK`: on darwin → `CLOCK_MONOTONIC_RAW`, on
  other POSIX → `CLOCK_MONOTONIC`, fallback → `CLOCK_REALTIME`.
  `PG_INSTR_SYSTEM_CLOCK_NAME` is a string for log output.
  [from-comment]

### Lower-level conversions

- `pg_get_ticks_system()` — inline; reads the platform clock.
- `pg_ticks_to_ns(ticks)` — handles the overflow-safe two-part
  path when `ticks > max_ticks_no_overflow`.
- `pg_ns_to_ticks(ns)` — inverse.

## Notable invariants / details

- "Note that INSTR_TIME_SUBTRACT and INSTR_TIME_ACCUM_DIFF convert
  absolute times to intervals. The INSTR_TIME_GET_xxx operations
  are only useful on intervals." Calling GET on an absolute time
  yields a meaningless huge number. [from-comment]
- "Beware of multiple evaluations of the macro arguments." Caller
  responsibility for any expression with a side effect.
  [from-comment]
- TSC frequency-scale changes (`ticks_per_ns_scaled` mutating
  between SET_CURRENT and GET) "will lead to incorrect results."
  The GUC is modifiable at runtime, with explicit caveats.
  [from-comment]
- On macOS the CLOCK_MONOTONIC_RAW path is "both faster to read
  and higher resolution than their version of CLOCK_MONOTONIC."
  [from-comment]
- TSC clock path bypasses `pg_get_ticks_system` entirely — it
  calls RDTSCP directly in architecture-specific code (further
  down in this file, not shown here).

## Potential issues

- `INSTR_TIME_SET_CURRENT_FAST` vs `INSTR_TIME_SET_CURRENT` — the
  difference matters for tight loops (FAST allows OOO,
  non-FAST forces RDTSCP). A reviewer must check that
  micro-benchmark code uses the right one. [ISSUE-doc-drift:
  FAST-vs-fenced semantics easy to confuse (nit)]
- `pg_set_timing_clock_source(TSC)` returning false when TSC is
  unavailable is the only signal; "frontend mistakenly assumes
  TSC and gets system clock" is silent. [ISSUE-question: should
  frontends ereport on fallback? (nit)]
- `timing_tsc_frequency_khz = -1` sentinel for "uninitialized"
  conflicts with `int32` signedness in a way that's safe today
  (frequencies are positive) but a future migration to uint32
  would corrupt the uninit signal. [ISSUE-undocumented-invariant:
  -1 sentinel on signed int (nit)]
- `pg_get_ticks_system` uses `Assert(timing_initialized)` —
  release builds will silently return whatever the clock yields
  before init. [ISSUE-correctness: release-build missing-init
  goes undetected (nit)]
- `frequency_source[128]` is a fixed-size string buffer — long
  CPUID-derived names could be silently truncated.
  [ISSUE-question: 128 bytes enough for all CPUID strings?
  (nit)]
