# `src/include/storage/predicate_internals.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 530+ (substantially larger than `predicate.h`)

## Role

Private-to-SSI definitions: `SERIALIZABLEXACT`, predicate-lock
hashtable layouts, `SerCommitSeqNo` ordering, SLRU state for
serial-list, two-phase commit serialization, page-tuple-lock
tracking. Exposed in a header (rather than purely in
`predicate.c`) because parallel-query workers, 2PC recovery, and
some pg_stat plumbing reach into these.

## Key types

- `SerCommitSeqNo` — `uint64`. Reserved values:
  - `0` (non-existent SLRU entry; can NEVER be a SerCommitSeqNo)
  - `InvalidSerCommitSeqNo = PG_UINT64_MAX` — uncommitted xact
  - `RecoverySerCommitSeqNo = 1` — pre-crash recovered xact
  - `FirstNormalSerCommitSeqNo = 2`
  [verified-by-code]
  `source/src/include/storage/predicate_internals.h:24-40`
- `SERIALIZABLEXACT` — per-xact state in shmem with
  `prepareSeqNo`/`commitSeqNo` ordering, conflict-in/out lists,
  finishedBefore stamp for cleanup eligibility.
  [verified-by-code] lines 58-...
- The serial-SLRU at `pg_serial/` tracks SerCommitSeqNo →
  conflict info for committed xacts that can still serialize
  with a live reader.

## Invariants

- INV-1: `SERIALIZABLEXACT` entries live until
  `finishedBefore <= SxactGlobalXmin`. Premature cleanup =
  missed conflicts = serialization anomaly. [from-comment]
  lines 50-56.
- INV-2: SerCommitSeqNo monotonic but NOT strict order across
  prepare/commit (the two-number trick at lines 62-75).
  Conservative — false-positive conflicts but never missed.
- INV-3: cleanup of read-only xacts is optimized (lines 50-54
  refer to "special optimizations for READ ONLY").

## Trust boundary (Phase D)

- Header is internal-only but visible to FRONTEND headers via
  transitive include (`storage/lock.h` → here). No external
  consumers from extensions in core.
- 2PC interaction: a prepared transaction's predicate-lock
  state persists across crashes; corruption of SLRU entries
  could cause spurious or missing conflicts. Filesystem
  permissions on `$PGDATA/pg_serial/` are the perimeter.

## Cross-refs

- `knowledge/files/src/include/storage/predicate.h.md`
- `knowledge/files/src/backend/storage/lmgr/predicate.c.md`
  (if exists)
- README: `src/backend/storage/lmgr/README-SSI`

## Issues

None directly at the header level.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-lmgr.md](../../../../subsystems/storage-lmgr.md)
