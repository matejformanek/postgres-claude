# PgStat_Counter — the cumulative-stats type

`PgStat_Counter` is the canonical `int64` event-counter used
throughout PostgreSQL's cumulative statistics subsystem. Every
"number of times X happened since the cluster started" value
you see in `pg_stat_*` views is a `PgStat_Counter` somewhere in
shared memory plus a backend-local pending accumulator. The
type itself is trivial; the surrounding accumulation /
flush / propagation machinery is where the design pressure is.

Anchors:
- `source/src/include/pgstat.h:71` — the typedef
  [verified-by-code]
- `source/src/include/pgstat.h:85-210` — the per-counter
  family structs (TableCounts, BgWriterStats, etc.)
- `source/src/backend/utils/activity/` — pgstat implementation
- `knowledge/idioms/cache-invalidation-registration.md` —
  pgstat registers inval callbacks too

## Definition

```c
typedef int64 PgStat_Counter;
```

[verified-by-code `pgstat.h:71`]

That's it. Signed 64-bit integer. The simplicity is the point —
counters propagate freely between backend, dshash, and on-disk
formats without conversion. Even derived stats like average
times are computed by client SQL as `sum_time / num_calls`,
not stored pre-averaged.

## Why `int64`, not `uint64`?

`delta_live_tuples` and `delta_dead_tuples` go negative — a
DELETE produces negative live deltas. `[from-comment
pgstat.h:138-140]` "Note that delta_live_tuples and
delta_dead_tuples can be negative!"

Most other counters are non-negative, but using a uniform
signed type means there's no risk of a developer accidentally
declaring a delta as `PgStat_Counter`, expecting unsigned
semantics, and getting absurd values on wraparound.

## The counter families

[verified-by-code `pgstat.h` struct definitions]

### Per-table (PgStat_TableCounts)

```c
typedef struct PgStat_TableCounts
{
    PgStat_Counter numscans;
    PgStat_Counter tuples_returned, tuples_fetched;
    PgStat_Counter tuples_inserted, tuples_updated, tuples_deleted;
    PgStat_Counter tuples_hot_updated, tuples_newpage_updated;
    bool           truncdropped;
    PgStat_Counter delta_live_tuples, delta_dead_tuples;
    PgStat_Counter changed_tuples;
    PgStat_Counter blocks_fetched, blocks_hit;
} PgStat_TableCounts;
```

[verified-by-code `pgstat.h:143-163`]

Per-table is the broadest counter set. `tuples_returned` =
heap_getnext results; `tuples_fetched` = heap_fetch results
under bitmap-scan control [from-comment `pgstat.h:130-135`].

### Per-function (PgStat_FunctionCounts)

```c
typedef struct PgStat_FunctionCounts
{
    PgStat_Counter numcalls;
    instr_time     total_time;
    instr_time     self_time;
} PgStat_FunctionCounts;
```

`instr_time` is the high-res timer; only `PgStat_Counter` for
the call count. Time fields convert to `PgStat_Counter`-as-
microseconds when flushing to shared memory
[from-comment `pgstat.h:82-83`].

### Per-subscription (PgStat_BackendSubEntry)

```c
typedef struct PgStat_BackendSubEntry
{
    PgStat_Counter apply_error_count;
    PgStat_Counter sync_seq_error_count;
    PgStat_Counter sync_table_error_count;
    PgStat_Counter conflict_count[CONFLICT_NUM_TYPES];
} PgStat_BackendSubEntry;
```

Logical-replication subscriber-side errors.

### Per-cluster (PgStat_ArchiverStats, BgWriterStats, etc.)

Each subsystem (archiver, bgwriter, checkpointer, slru, wal)
has its own `PgStat_*Stats` struct; all consist of
`PgStat_Counter` fields + a `stat_reset_timestamp`.

## The pending-flush pattern

A counter on a hot path can't acquire a lock per increment.
Pgstat handles this with a two-stage flow:

1. **Backend-local pending state** — incremented without locking
   in `PgStat_TableStatus.counts.*`. No contention.
2. **Flush to shared dshash** at transaction boundaries or
   periodic intervals (`pgstat_report_stat()` walks the pending
   list and atomically adds to shared counters).

This is why "you just executed an INSERT but `pg_stat_user_tables`
shows 0" — the increment is in pending, not yet flushed. The
flush happens on transaction commit or every
`PGSTAT_MIN_INTERVAL` milliseconds, whichever first.

## Transactional vs non-transactional counters

[from-comment `pgstat.h:168-178`]

> Many of the event counters are nontransactional, ie, we count
> events in committed and aborted transactions alike.

`numscans`, `tuples_returned`, `tuples_inserted`, etc. count
*attempts*, not *successes*. An aborted INSERT still increments
`tuples_inserted` — because the I/O cost was real.

But `delta_live_tuples`, `delta_dead_tuples`, `changed_tuples`
are **transactional** — propagated via a per-subxact stack
(`PgStat_TableXactStatus`)
[verified-by-code `pgstat.h:193-210`]. On commit, the
subxact's deltas roll up to the parent or to the table-level
counts. On abort, they vanish.

This split is why `pg_stat_user_tables.n_tup_ins` and
`pg_stat_user_tables.n_live_tup` can diverge wildly — one
counts attempts, the other counts net effect.

## Reset semantics

Every per-cluster stats struct carries a
`stat_reset_timestamp`. `pg_stat_reset*()` SQL functions zero
the counters AND bump this timestamp. The reset is broadcast
through the standard pgstat shared-memory flush — backends
notice on their next flush.

`pg_stat_reset_subscription_stats` and a few others have
narrower scope (one subscription, one slot); same pattern.

## On-disk format compatibility

[verified-by-code `pgstat.h:221`]

```c
#define PGSTAT_FILE_FORMAT_ID    0x01A5BCBC
```

Any change to a `PgStat_*` struct that flushes to disk MUST
bump this magic. Forgetting = corrupt stats files on minor
upgrade, possible SIGSEGV at startup. The patch-submission
checklist includes this; it's a frequent review catch.

## Common review-time concerns

- **New counter on a hot path** → backend-local pending
  + flush on commit. Do NOT atomically increment a shared
  counter per tuple; you'll serialize the workload.
- **New `PgStat_*` struct flushed to disk** → bump
  `PGSTAT_FILE_FORMAT_ID`.
- **New transactional counter** → add to the
  `PgStat_TableXactStatus` propagation. Just adding a field to
  `PgStat_TableCounts` skips the per-subxact accounting and
  the count is wrong on rollback.
- **Negative-capable delta**? Use `PgStat_Counter` (signed
  int64). Don't try to enforce `uint64`.
- **Reset semantics** — make sure the reset SQL function
  re-initializes your new counter too.

## Invariants

- **[INV-1]** `PgStat_Counter` is `int64`; signed semantics
  enforced.
- **[INV-2]** Non-transactional counters increment on both
  commit AND abort (attempts, not successes).
- **[INV-3]** Transactional counters (`delta_*`,
  `changed_tuples`) propagate via subxact stack; aborted
  subxacts forfeit their contribution.
- **[INV-4]** Disk-flushed struct changes MUST bump
  `PGSTAT_FILE_FORMAT_ID`.
- **[INV-5]** Backend-local pending + periodic flush is the
  canonical hot-path pattern; never atomic-add to shared
  counters per tuple.

## Useful greps

- All counters in pgstat.h:
  `grep -n 'PgStat_Counter' source/src/include/pgstat.h | head -40`
- The flush entry point:
  `grep -RIn 'pgstat_report_stat\b' source/src/backend/utils/activity`
- Per-table struct sites:
  `grep -RIn 'PgStat_TableCounts\|PgStat_TableStatus' source/src/backend | head -20`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/activity/pgstat.c`](../files/src/backend/utils/activity/pgstat.c.md) | — | flush / reset / shared-state management |
| [`src/include/pgstat.h`](../files/src/include/pgstat.h.md) | 71 | typedef |
| [`src/include/pgstat.h`](../files/src/include/pgstat.h.md) | 85 | the per-counter family structs (TableCounts, BgWriterStats, etc.) |
| [`src/include/pgstat.h`](../files/src/include/pgstat.h.md) | — | public type + struct family |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/subsystems/utils-mmgr.md` — memory-context
  patterns; pgstat pending state lives in backend-local
  contexts.
- `.claude/skills/debugging/SKILL.md` — `pg_stat_*` views are
  the first stop for "what's the database actually doing."
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL stats
  (`PgStat_WalStats`) follow this pattern too.
- `knowledge/idioms/cache-invalidation-registration.md` —
  pgstat registers reset callbacks via this API.
- `source/src/include/pgstat.h` — public type + struct
  family.
- `source/src/backend/utils/activity/pgstat.c` — flush /
  reset / shared-state management.
- `source/src/backend/utils/activity/pgstat_*.c` — per-kind
  implementations (one file per counter family).
