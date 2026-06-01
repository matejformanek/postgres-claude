# nodeSamplescan.c

- **Source:** `source/src/backend/executor/nodeSamplescan.c` (≈320 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

`TABLESAMPLE` driver. Delegates the row-selection logic to a pluggable
TABLESAMPLE method (TsmRoutine) registered for the chosen method (BERNOULLI,
SYSTEM, SYSTEM_ROWS, SYSTEM_TIME via `tsm_system_*` extensions).

## Mechanics

- `tablesample_init(scanstate)` — calls the TsmRoutine's `InitSampleScan`
  callback, which validates the REPEATABLE seed and any method-specific
  args.
- `SampleNext(scanstate)` — drives the per-block / per-tuple sampling:
  - `NextSampleBlock(scandesc)` — method picks the next BlockNumber (or
    "all" for BERNOULLI).
  - `NextSampleTuple(scandesc, blockno, maxoffset)` — method picks an
    OffsetNumber within the page.
- Fetches via `table_scan_sample_next_block` / `table_scan_sample_next_tuple`
  in tableam.

## Tags

- [verified-by-code] TsmRoutine callback usage.
- [from-comment] file-level intent (extension-pluggable sampling methods).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
