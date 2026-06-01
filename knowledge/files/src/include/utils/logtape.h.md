# `src/include/utils/logtape.h`

- **File:** `source/src/include/utils/logtape.h` (77 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Public interface for `logtape.c` — the multi-tape-multiplexing-into-one-
BufFile bookkeeping that powers tuplesort's space-recycling external
sort. Type details are deliberately hidden behind opaque
`LogicalTapeSet` / `LogicalTape` forward declarations (`logtape.h:25-26`).

## Public types

- **`LogicalTapeSet`** (`:25`) — the per-sort container holding
  `BufFile`, freelist, allocation/written/hole counters.
- **`LogicalTape`** (`:26`) — one logical tape within the set.
- **`TapeShare { int64 firstblocknumber; }`** (`:48-55`) — DSM-resident
  metadata workers hand to the leader during parallel sort. The comment
  block `:29-47` documents the parallel-sort handoff: workers freeze
  their final materialized tape and export a `TapeShare`; the leader
  combines all the workers' `TapeShare`s via `LogicalTapeImport`. It
  also notes that the leader's own appended-empty tape is **never
  writable** "due to a restriction in the shared buffile infrastructure"
  (`:44-46` [from-comment]).

## API surface

Set lifecycle:
- `LogicalTapeSetCreate(preallocate, fileset, worker)` (`:61`) —
  `fileset != NULL` is the SharedFileSet (parallel) path.
- `LogicalTapeSetClose` (`:64`).
- `LogicalTapeSetForgetFreeSpace` (`:67`) — stop tracking recycled blocks
  (final-merge optimization).
- `LogicalTapeSetBlocks` (`:75`) — `nBlocksWritten - nHoleBlocks`.

Per-tape:
- `LogicalTapeCreate(lts)` (`:65`) — new write tape.
- `LogicalTapeImport(lts, worker, share)` (`:66`) — import a
  worker-frozen tape.
- `LogicalTapeClose` (`:63`).
- `LogicalTapeFreeze(lt, share)` (`:71`) — finalize for random-access
  reading. When `share != NULL`, fills in `TapeShare` (parallel-worker
  exit path).
- `LogicalTapeRewindForRead(lt, buffer_size)` (`:70`) — flush write
  buffer, switch to read mode with the given prefetch buffer size.

I/O:
- `LogicalTapeRead`, `LogicalTapeWrite`, `LogicalTapeBackspace`,
  `LogicalTapeSeek`, `LogicalTapeTell`.

## Cross-references

- `source/src/backend/utils/sort/logtape.c` — implementation.
- `source/src/include/storage/sharedfileset.h` — the `SharedFileSet`
  used in `LogicalTapeSetCreate`.
- `tuplesort.c`, `nodeAgg.c` (HashAgg spill) — consumers.

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 2
