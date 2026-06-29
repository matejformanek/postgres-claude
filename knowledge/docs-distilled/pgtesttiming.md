---
source_url: https://www.postgresql.org/docs/current/pgtesttiming.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_test_timing — measure timing-call overhead behind EXPLAIN ANALYZE

`pg_test_timing` measures the per-call overhead and resolution of the system
timer (`gettimeofday`/`clock_gettime`) that PostgreSQL uses for `EXPLAIN
ANALYZE` row timing and `track_io_timing`. A slow clock source makes that
instrumentation expensive enough to *distort the very thing it measures*.
`[from-docs]`

## Non-obvious claims

- **The instrumentation can dominate the measurement.** The docs' worked
  example: a query ran ~9.8 ms raw but ~16.6 ms under `EXPLAIN ANALYZE` — ~6.8 ms
  was pure timing overhead. On the slow `acpi_pm` clock the overhead can swamp
  the query cost entirely. `[from-docs]`
- **Clock source is the lever, and it's a ~20× swing.** On one Intel i7-860 the
  per-loop overhead was ~36 ns on `tsc` vs ~723 ns on `acpi_pm` — same hardware,
  different `clocksource`. `[from-docs]`
- **Histogram bucketed by powers of two** (<1µs, 2µs, 4µs, …). Good clock: >90%
  of calls in the <1µs bucket. Bad clock: most calls in the 2µs bucket with a
  long tail. Per-loop overhead >100 ns is the red flag. `[from-docs]`
- **TSC is fastest (~1 ns) but historically unreliable** — temperature drift on
  old CPUs, cross-core inconsistency (time going backwards), and aggressive
  power management can make the OS demote it to HPET (~100 ns) or `acpi_pm`
  (~300 ns). `[from-docs]`
- **Mitigation when the clock is bad:** run `EXPLAIN (ANALYZE, TIMING OFF)` to
  keep row counts without paying the timing tax. `[from-docs]`

## Linux clocksource control

```
cat /sys/devices/system/clocksource/clocksource0/current_clocksource     # e.g. tsc
cat /sys/devices/system/clocksource/clocksource0/available_clocksource    # tsc hpet acpi_pm
# echo hpet > .../current_clocksource    # change (root)
```

## Options

| Flag | Meaning |
|---|---|
| `-d`, `--duration=SECONDS` | Test length (default 3); longer is more likely to surface clock anomalies. |
| `-c`, `--cutoff=PCT` | Histogram cutoff percentile for the per-duration report. `[unverified — present in recent PG versions; not confirmed in this fetch]` |

## Links into corpus

- `[[knowledge/docs-distilled/monitoring-stats.md]]` — `track_io_timing` and the
  cost of I/O timing this tool characterizes.
- `[[knowledge/docs-distilled/dynamic-trace.md]]` — the other "instrument the
  backend without distorting it" surface.
- `[[knowledge/docs-distilled/pgtestfsync.md]]` — sibling micro-benchmark in the
  same Reference family.
- Skill: `debugging`, `executor-and-planner` (EXPLAIN ANALYZE), `testing`.
