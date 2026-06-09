# `src/include/utils/sharedtuplestore.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Multi-writer / multi-reader tuple storage shared between parallel
backends, backed by `SharedFileSet` temp files [from-comment:
lines 3-5]. Primary client: Parallel Hash Join batch files
(`executor/hashjoin.h`).

## Public API

[verified-by-code: lines 20-59]

- `SharedTuplestore` — opaque shared-mem state.
- `SharedTuplestoreAccessor` — per-participant local handle.
- Flag `SHARED_TUPLESTORE_SINGLE_PASS` — promises one scan only,
  enabling early unlink of backing files [lines 26-30].

Functions:
- `sts_estimate(participants)` — size for DSM allocation.
- `sts_initialize(sts, participants, my_participant_number,
  meta_data_size, flags, fileset, name)` — first participant
  initializes.
- `sts_attach(sts, my_participant_number, fileset)` — later
  participants attach.
- `sts_end_write(accessor)` — close write side for this
  participant.
- `sts_reinitialize(accessor)` — rewind for a new pass.
- `sts_begin_parallel_scan` / `sts_end_parallel_scan`.
- `sts_puttuple(accessor, meta_data, MinimalTuple)`.
- `sts_parallel_scan_next(accessor, meta_data) -> MinimalTuple`.

## Invariants

- **INV-PARTICIPANTS** [inferred] `participants` is fixed at
  initialization; each backend uses a distinct
  `my_participant_number` in `[0, participants)`. No dynamic
  resize.
- **INV-FILESET** [verified-by-code: lines 18, 38] All backing
  files live in a caller-provided `SharedFileSet` — cleanup happens
  when the fileset is destroyed (typically at end of parallel
  query).
- **INV-MIN-TUPLE-FORMAT** [verified-by-code: lines 54, 58] Tuples
  are stored as `MinimalTuple`; not raw HeapTuples.
- **INV-SINGLE-PASS** [from-comment: lines 26-30] When
  `SHARED_TUPLESTORE_SINGLE_PASS` is set, files may be unlinked
  before all readers finish if they've been drained — caller must
  not rescan.

## Trust boundary (Phase D)

- **Spill files location**: under `pgsql_tmp/` in the configured
  temp tablespace; permissions are postgres-user. A second OS
  process running as the postgres OS user can read the spill (same
  posture as ordinary `BufFile`).
- **No encryption**: spill files contain raw `MinimalTuple` bytes
  including all column values for the parallel-hash inner / outer
  side. PII / secret values in joined columns hit disk.
- **Cleanup**: relies on `SharedFileSet` teardown via
  `ResourceOwner`; a crashed worker that left files behind is
  cleaned up by the next startup's `pgsql_tmp/` purge.

## Cross-refs

- `storage/sharedfileset.h` — backing fileset.
- `executor/hashjoin.h` — primary user
  (`ParallelHashJoinBatch{Inner,Outer}` macros wrap STS).
- `access/htup.h` — `MinimalTuple`.

## Issues

- [ISSUE-PHASE-D: spill files contain raw column data (no
  encryption); cross-process leak to another postgres-uid process
  is feasible (medium, same posture as all PG temp files)] —
  lines 38-44.
- [ISSUE-API: no header-level statement that `meta_data_size` must
  match between writer and reader; mismatch is silent corruption
  (low)] — line 37.
