# src/include/replication/conflict.h

## Purpose

Conflict-logging API for the logical-replication **apply worker**.
Enumerates the conflict types the apply worker can detect when applying
a remote change locally, plus the report-and-log entry points.

## Role in PG

When the subscriber's apply worker applies a remote INSERT/UPDATE/DELETE,
the local table may already be in a state that conflicts: row missing,
already exists, modified by a different origin, etc. This header
classifies those situations and provides `ReportApplyConflict` to log
them (and increment `pg_stat_subscription_stats.conflict_count`
buckets). PG18 added the apply-time conflict-detection enhancements
visible here (origin-differs detection, multiple-unique-conflict).

Copyright header (line 5): "Copyright (c) 2024-2026" — feature is
recent. The current default behavior on most conflict types is to error
out and stall the apply worker; conflict resolution policies (skip,
overwrite) are still in flux upstream and not yet in this header.

## Key types/struct fields

- `ConflictType` enum (lines 31-62) — eight types:
  - `CT_INSERT_EXISTS` — incoming INSERT hits unique constraint.
  - `CT_UPDATE_ORIGIN_DIFFERS` — local row was last modified by a
    different origin (cross-replication-stream conflict).
  - `CT_UPDATE_EXISTS` — UPDATE's new value hits unique constraint.
  - `CT_UPDATE_DELETED` — local row was concurrently deleted by another
    origin.
  - `CT_UPDATE_MISSING` — UPDATE target row not found.
  - `CT_DELETE_ORIGIN_DIFFERS` — local row last modified by other
    origin.
  - `CT_DELETE_MISSING` — DELETE target not found.
  - `CT_MULTIPLE_UNIQUE_CONFLICTS` — incoming row hits >1 unique
    constraint.
  [verified-by-code]

- Trailing comment (lines 57-61) explicitly defers exclusion-constraint
  conflicts to future work. [from-comment]

- `CONFLICT_NUM_TYPES` macro (line 64) — `CT_MULTIPLE_UNIQUE_CONFLICTS
  + 1`. Used to size the per-subscription stats array
  `PgStat_StatSubEntry::conflict_count[]`. Header comment (lines 26-29)
  warns: reordering or adding enum values requires updating stats
  collection code. [verified-by-code]

- `ConflictTupleInfo` (lines 69-80) — describes a single local tuple
  that caused a conflict:
  - `slot` (TupleTableSlot) — the conflicting local tuple.
  - `indexoid` — which unique index detected the conflict.
  - `xmin` — TransactionId of the modification that put the local row
    in the way.
  - `origin` (ReplOriginId) — origin (replication source) of that
    modification.
  - `ts` (TimestampTz) — when the modification happened.
  [verified-by-code]

- Functions (lines 82-91):
  - `GetTupleTransactionInfo(slot, &xmin, &origin, &ts)` — extract the
    conflict-relevant metadata from a TupleTableSlot. Reads
    HeapTupleHeader fields and the replication-origin commit log.
  - `ReportApplyConflict(estate, relinfo, elevel, type, searchslot,
    remoteslot, conflicttuples)` — emit the log line + increment
    stats. Takes a list of `ConflictTupleInfo`s because
    multiple-unique-conflict can collide on >1 row simultaneously.
    `elevel` is caller-chosen (typically LOG or ERROR), foreshadowing
    a future conflict-resolution policy GUC.
  - `InitConflictIndexes(relinfo)` — pre-compute the per-relation list
    of unique-constraint indexes used during apply conflict detection.
  [verified-by-code]

## Phase D notes

**Conflict-resolution policy.** The `elevel` parameter on
`ReportApplyConflict` is the only existing hook for a future "skip vs
error vs apply" policy. As of the pinned commit, callers pass ERROR or
LOG; there's no GUC selecting between (e.g.) "remote wins" /
"local wins" / "last-write-wins by timestamp". A future patch adding
this will likely:
1. Extend `ConflictType` (warning in header comment about stats arrays
   becomes load-bearing).
2. Add per-subscription configuration carrying the policy.
3. Branch in `ReportApplyConflict` on policy: log+continue, log+error,
   log+overwrite.
[inferred]

**Origin-differs as a conflict signal.** `CT_UPDATE_ORIGIN_DIFFERS` /
`CT_DELETE_ORIGIN_DIFFERS` require that the local tuple header records
the replication origin of its last update (track_commit_timestamp +
the origin commit log machinery). Without
`track_commit_timestamp=on`, origin info is unavailable and these
checks silently fall back to no-conflict-detected — a CONFIGURATION
gotcha that the header doesn't flag. [inferred — needs verification in
the apply worker]

**Statistics enum coupling.** The header comment (lines 26-29) warns
about the stats coupling but doesn't say WHERE the stats code lives —
hunting via grep needed (`PgStat_StatSubEntry::conflict_count` in
`utils/activity/pgstat_subscription.c` or similar). Order-dependent
arrays are a classic ABI hazard between minor versions if a backpatch
inserts an enum value mid-list. [from-comment]

## Potential issues

- [ISSUE-undocumented-invariant: origin-based conflict detection
  silently degrades when `track_commit_timestamp=off`; header gives no
  hint (maybe)]
- [ISSUE-stale-todo: comment lines 57-61 defers exclusion-constraint
  conflict types "for future improvements"; needs a tracking note in
  TODO/wiki (low)]
- [ISSUE-undocumented-invariant: enum reordering breaks stats arrays;
  comment lines 26-29 warns but no compile-time assertion ties
  `CONFLICT_NUM_TYPES` to the stats array size (maybe)]
- [ISSUE-state-transition: `elevel` parameter implies but does not
  document a planned conflict-resolution policy; calling-convention
  contract (when LOG vs ERROR) lives only in apply worker (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
