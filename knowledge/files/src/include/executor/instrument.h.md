# instrument.h

- **Source:** `source/src/include/executor/instrument.h` (158 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## Purpose

Public surface of the EXPLAIN ANALYZE / pg_stat_statements / auto_explain
instrumentation system.

## Counter structs

- `BufferUsage` — `shared_blks_{hit,read,dirtied,written}`,
  `local_blks_*`, `temp_blks_{read,written}`, `shared_blk_{read,write}_time`,
  `local_blk_{read,write}_time`, `temp_blk_{read,write}_time`.
  **Monotonically increasing, never reset** — code diffs snapshots.
- `WalUsage` — `wal_records`, `wal_fpi`, `wal_bytes`, `wal_buffers_full`.
- `Instrumentation` (defined in instrument_node.h) — per-PlanState
  accumulator: `running, starttime, counter, firsttuple, total_time,
  ntuples, ntuples2, nloops, startup, min/max_t, bufusage, walusage,
  bufusage_start, walusage_start`.

## Per-process globals

`extern BufferUsage pgBufferUsage;` and `extern WalUsage pgWalUsage;` — every
buffer / WAL operation in the backend adds to these. The diff pattern is
what enables per-node attribution.

## INSTRUMENT_* option bits

- `INSTRUMENT_TIMER` (4) — record per-node timings.
- `INSTRUMENT_BUFFERS` (8) — record buffer usage.
- `INSTRUMENT_ROWS` (1) — record row counts.
- `INSTRUMENT_WAL` (16) — record WAL usage (for DML / index build).
- `INSTRUMENT_ALL = ~0`.

## Functions

`InstrAlloc`, `InstrInit`, `InstrStartNode`, `InstrStopNode`, `InstrEndLoop`,
`InstrAggNode`, `InstrJitSummary`, `BufferUsageAccumDiff`, `WalUsageAccumDiff`.

## Tags

- [verified-by-code] every struct + global.
- [from-comment] monotonicity invariant at file head.
