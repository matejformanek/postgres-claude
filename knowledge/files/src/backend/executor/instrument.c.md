# instrument.c

- **Source:** `source/src/backend/executor/instrument.c` (446 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

`Instrumentation` accounting struct attached to a PlanState — populated by
EXPLAIN ANALYZE (and by pg_stat_statements / auto_explain via the same path)
to track per-node timing, row counts, loop counts, buffer usage, WAL usage,
and JIT timing.

## Globals

- `BufferUsage pgBufferUsage` `:25` — process-wide cumulative buffer hit /
  read / dirtied / written counts. Each `InstrStartNode` snapshots it; each
  `InstrStopNode` diffs into the node's per-loop counters. This is how
  EXPLAIN (BUFFERS) per-node attribution works.
- `WalUsage pgWalUsage` `:27` — same trick for WAL records / bytes / FPI.

## API

- `InstrAlloc(int n_info, int instrument_options, bool async_mode)` — allocate
  one Instrumentation per PlanState the caller wants to track. `instrument_options`
  is a bitmask of INSTRUMENT_TIMER, INSTRUMENT_BUFFERS, INSTRUMENT_ROWS,
  INSTRUMENT_WAL.
- `InstrInit(instr, options)` — zero out per-loop counters.
- `InstrStartNode(instr)` — record start time + snapshot of pgBufferUsage/pgWalUsage.
- `InstrStopNode(instr, nTuples)` — accumulate diff into per-loop counters.
- `InstrEndLoop(instr)` — at end of one outer loop, fold per-loop counters
  into the long-running totals + counters: `ntuples` (sum), `nloops` (count),
  `total_time`, `min_t / max_t`, etc.
- `InstrAggNode(target, add)` — merge a worker's Instrumentation into the
  leader's after parallel execution.
- `InstrJitSummary(JitInstrumentation)` — accumulate JIT counters from a
  parallel worker.
- `BufferUsageAccumDiff(dst, add, sub) ` — utility for the snapshot-diff
  pattern used everywhere.

## EXPLAIN-side consumers

`explain.c` reads `nloops`, `total_time / nloops` for "actual time"; for
`(BUFFERS)`, reads the `bufusage` struct; for parallel-aware nodes, prints
per-worker stats from the array filled in by `ExecParallelFinish`.

## Tags

- [verified-by-code] global names + the snapshot-diff pattern.
- [inferred] use by explain.c (consistent with how EXPLAIN ANALYZE works).
