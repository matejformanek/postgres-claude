# `src/include/utils/pgstat_internal.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

The internal architecture of the cumulative-stats system — definitions
needed only by files implementing stats support, not by callers that
just report or query stats [from-comment: lines 4-7]. Holds the
shared-memory hashtable design, per-entry refcount discipline,
transactional drop tracking, and the `PgStat_KindInfo` callback vtable
that pluggable stats kinds implement.

## Public API surface (types + key callbacks)

[verified-by-code]

- `PgStat_HashKey {kind, dboid, objid}` — 16 bytes, **no padding**
  (asserted at compile time, lines 85-87). Used as key in shared
  dshash.
- `PgStatShared_HashEntry` (lines 94-145) — `{key, dropped, refcount
  (atomic), generation (atomic), body}`. Lifetime: even after `DROP
  TABLE` sets `dropped=true`, entry persists until refcount hits 0
  [lines 99-103].
- `PgStatShared_Common` (lines 150-155) — embedded header of every
  kind-specific stats struct: `{magic, LWLock lock}`.
- `PgStat_EntryRef` (lines 164-193) — backend-local handle pointing
  into shared hash, optionally with `pending` per-backend delta.
- `PgStat_StatsFileOp` enum — STATS_WRITE / STATS_READ /
  STATS_DISCARD; passed to `finish` callback.
- `PgStat_SubXactStatus` (lines 201-225) — per-subxact pending drops
  and per-table xact counters; cleaned at sub/top commit/abort.
- `PgStat_KindInfo` (lines 231-384) — the vtable. Required fields per
  kind: `fixed_amount`, `accessed_across_databases`, `write_to_file`,
  `track_entry_count`, sizes/offsets, and callback funptrs
  (`init_backend_cb`, `flush_pending_cb`, `delete_pending_cb`,
  `reset_timestamp_cb`, `(to|from)_serialized_(name|data)`, `finish`,
  `init_shmem_cb`, `flush_static_cb`, `reset_all_cb`, `snapshot_cb`).
- `slru_names[]` (lines 395-404) — fixed list ending in `"other"` for
  extension SLRUs without an entry; `SLRU_NUM_ELEMENTS` derived.

(Full file is ~1059 lines; remaining material is the per-kind shared
structs `PgStatShared_Database`, `PgStatShared_Relation` etc., the
on-disk file constants `PGSTAT_FILE_FORMAT_ID`,
`PGSTAT_STAT_PERMANENT_FILENAME`, and prototypes per
`pgstat_<kind>.c` file.)

## Invariants

- **INV-NOPAD** [verified-by-code: line 85] `sizeof(PgStat_HashKey)`
  must equal `sizeof(kind) + sizeof(uint64) + sizeof(Oid)` —
  enforced by `StaticAssertDecl`.
- **INV-OBJID-WIDTH** [from-comment: lines 56-58] `objid` is uint64;
  comment says 8 bytes are "good enough" — **adding fields to
  `PgStat_HashKey` is discouraged** because dshash performance is
  sensitive to key width.
- **INV-REFCOUNT** [from-comment: lines 99-124] Entry refcount may
  be incremented/decremented under a shared lock on the dshash
  partition; entry can only be freed when refcount drops to 0;
  `dropped` is a one-way flag.
- **INV-GENERATION** [from-comment: lines 127-137] Bumped on every
  `pgstat_reinit_entry()`; lets backends detect a recycled slot
  without holding the partition lock.
- **INV-PENDING** [from-comment: lines 158-193] Pending stats live in
  backend-local memory; flushed via `flush_pending_cb`. A kind
  without pending data must set `pending_size = 0`.
- **INV-SUBXACT-DROPS** [from-comment: lines 207-213] Stats drops are
  recorded in commit/abort WAL records so replicas and crashes
  converge.

## Trust boundary (Phase D)

- **Custom stats kinds** [from-comment: lines 296-340 callbacks +
  `pgstat_kind.h` IDs 24..32]: an extension supplying a
  `PgStat_KindInfo` runs arbitrary C in the stats system's locks.
  `init_shmem_cb` runs at postmaster start in the postmaster context;
  `from_serialized_data` runs at startup while reading the on-disk
  stats file. A buggy callback there can take down the cluster.
- **On-disk stats file deserialization**
  (`from_serialized_data`/`from_serialized_name`): trust-on-disk —
  the stats file isn't WAL-logged, can be deleted on startup
  ("STATS_DISCARD"), and is regenerated. But a custom kind that
  trusts the file too much could be tricked by a hand-edited
  `pg_stat/pgstat.stat`.
- **`accessed_across_databases` flag** [from-comment: lines 240-243]:
  determines whether a kind's stats leak across database boundaries
  via snapshots. A custom kind that mis-sets this can expose data to
  unrelated databases.
- **LWLock embedded per entry** (`PgStatShared_Common.lock`): a
  buggy kind that holds this lock too long stalls *all* readers
  (the lock is per-entry but the dshash partition above it isn't).

## Cross-refs

- `pgstat_kind.h` — kind ID assignment, custom range 24..32.
- `backend_status.h` — separate per-backend status array (not
  cumulative).
- `lib/dshash.h` — backing dshash table.
- A11 monitoring-extraction cluster; A14 `pg_buffercache` /
  `pg_visibility` similar shared-stats reading patterns.

## Issues

- [ISSUE-DESIGN: serialization callbacks `(from|to)_serialized_data`
  run at backend startup before authentication completes for any
  backend that reads stats; a buggy custom-kind deserializer can
  delay or fault every fork (medium)] — lines 320-340.
- [ISSUE-API: `accessed_across_databases` policy is enforced only by
  this flag; no compile-time check that callbacks respect it (low)]
  — lines 240-243.
- [ISSUE-DOC: header doesn't enumerate which callbacks are mandatory
  vs optional in one place; "Required if" / "Optional" is scattered
  (low)] — lines 296-380.
