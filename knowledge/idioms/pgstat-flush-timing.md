# Pgstat flush timing — pending → shared dshash cadence

PG's cumulative statistics subsystem uses a **two-stage
write path**: per-backend pending state (incremented without
locking) flushes to shared `dshash` periodically. The timing
of the flush — when pending gets pushed to shared — is what
determines "I just ran a query but pg_stat_user_tables shows
0" surprises. The cadence is governed by
`PGSTAT_MIN_INTERVAL` / `PGSTAT_MAX_INTERVAL` plus transaction
boundaries.

Anchors:
- `source/src/backend/utils/activity/pgstat.c:127-129` —
  interval constants [verified-by-code]
- `source/src/backend/utils/activity/pgstat.c:191
  pgstat_flush_pending_entries` [verified-by-code]
- `knowledge/data-structures/pgstat-counter.md` — companion
  data-structure doc
- `.claude/skills/debugging/SKILL.md` — pg_stat_* views

## The two intervals

```c
#define PGSTAT_MIN_INTERVAL  1000    /* 1 second */
#define PGSTAT_MAX_INTERVAL 60000    /* 60 seconds */
```

[verified-by-code `pgstat.c:127-129`]

- **`PGSTAT_MIN_INTERVAL`** — minimum gap between consecutive
  flushes when not forced. Prevents flush thrashing under
  high-frequency calls.
- **`PGSTAT_MAX_INTERVAL`** — maximum gap before forced
  flush. Even an idle backend that hasn't done a transaction
  in 60s gets its pending state flushed.

## The pgstat_report_stat function

[verified-by-code `pgstat.c:709-713`]

```c
void pgstat_report_stat(bool force);
```

The entry point. Called:

1. **At transaction commit** (`AtEOXact_PgStat`) — `force =
   true`. The pending state for this xact's mutations flushes
   to shared.
2. **At transaction abort** — also forces flush; deltas
   computed differently.
3. **By the idle-backend wakeup** — periodic check at
   command-loop boundary.
4. **At backend exit** — final cleanup.

For `force = false`, the function:
- Checks `now() - last_flush_time < PGSTAT_MIN_INTERVAL` —
  if so, skip.
- Walks pending entries; tries `LWLockConditionalAcquire` on
  each target shared entry.
- If acquire succeeds, applies the pending counts; clears
  pending.
- If acquire fails (contended), leaves the pending for next
  iteration.

For `force = true`, the function blocks on locks rather than
skipping — guarantees the flush happens.

## The "force flush" force

The contract:

> Whenever pending stats updates remain at the end of
> pgstat_report_stat() a timeout is registered to call
> ourselves again, no longer than PGSTAT_MAX_INTERVAL...

[from-comment `pgstat.c:710-714`]

Even idle backends register a timeout to come back and try
again. The timeout is rescheduled until pending is empty.

This means: pgstat counters eventually become consistent
even if the backend stays idle. The "eventual" delay is at
most `PGSTAT_MAX_INTERVAL` = 60s.

## The "lock-contention skip"

The skip-on-contended-lock strategy is critical for
performance. Under high concurrency:

- Many backends try to flush their pending updates.
- The shared dshash bucket for a hot table is contended.
- Backends queue up.

With unconditional acquire: all backends block waiting on
the bucket lock → flush throughput drops.

With conditional acquire: contended backends try-and-skip,
deferring to the next iteration. The bucket processes one
backend's update at a time without forming a queue.

Result: aggregate stats accuracy is eventually consistent
without serializing the workload.

## The transaction-commit flush

At every successful transaction commit:

```c
pgstat_report_stat(true);
```

[verified-by-code `pgstat.c:604`]

The `true` forces the flush; the backend blocks on locks if
needed. This is the moment the backend's pending stats
become visible to other backends via the shared dshash.

So immediately after a commit, querying `pg_stat_*` views
sees the new stats. Querying mid-transaction (before commit)
sees pending state that the committing backend hasn't
flushed yet.

## What can cause "I committed but stats are stale"

Even after commit, the stats consumer might see stale
values:

1. **Stats reset in flight** — a `pg_stat_reset_*` call
   between commit and query.
2. **Reader doesn't refresh** — pg_stat_* views consult a
   per-backend snapshot that's updated at transaction
   start. Within a transaction, stats are point-in-time.
3. **Different database** — pg_stat_database is per-DB.

For real-time observability, `SELECT
pg_stat_clear_snapshot()` forces a fresh fetch.

## The autovacuum interaction

Autovacuum reads pg_stat_user_tables to find vacuum
candidates. If pgstat is slow to flush, autovacuum sees
stale `n_dead_tup` counts:

- May skip a table that's actually due.
- May vacuum a table that no longer needs it.

The naptime (default 60s) is intentionally aligned with
PGSTAT_MAX_INTERVAL — by the time autovacuum looks,
pgstat is current.

## The persistence layer

Every checkpoint, pgstat serializes the shared dshash to
`pg_stat/` on disk. On restart, the persisted state is
restored.

A crash mid-flush doesn't lose much — pending state in dying
backends is forfeit, but the shared dshash is recoverable.
Acceptable since pgstat is observability, not transactional
state.

## Common review-time concerns

- **Per-call flush is expensive.** Counters on hot paths
  should accumulate in pending; never atomic-add to shared
  per tuple.
- **For aggregated metrics**, leverage pgstat instead of
  custom counters.
- **Reset functions invalidate pending**; pending counters
  in flight at reset time may be lost.
- **`PGSTAT_MIN_INTERVAL` skip is a feature**, not a bug —
  the eventual consistency is by design.
- **Don't expect immediate visibility cross-backend.** A
  60s grace is the worst-case delay.

## Invariants

- **[INV-1]** Two-stage: backend pending → shared dshash on
  flush.
- **[INV-2]** PGSTAT_MIN_INTERVAL (1s) gates non-forced
  flushes.
- **[INV-3]** PGSTAT_MAX_INTERVAL (60s) is the worst-case
  staleness even for idle backends.
- **[INV-4]** Transaction commit always forces flush.
- **[INV-5]** Lock-contended flushes skip rather than
  queue.

## Useful greps

- The flush entry point:
  `grep -n 'pgstat_report_stat\|pgstat_flush_pending' source/src/backend/utils/activity/pgstat.c | head -10`
- The interval constants:
  `grep -n 'PGSTAT_MIN_INTERVAL\|PGSTAT_MAX_INTERVAL' source/src/backend/utils/activity/pgstat.c`
- The persistence layer:
  `grep -n 'pgstat_write_statsfile\|pgstat_read_statsfile' source/src/backend/utils/activity/pgstat.c | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/activity/pgstat.c`](../files/src/backend/utils/activity/pgstat.c.md) | 127 | interval constants |
| [`src/backend/utils/activity/pgstat.c`](../files/src/backend/utils/activity/pgstat.c.md) | 191 | pgstat_flush_pending_entries |
| [`src/backend/utils/activity/pgstat.c`](../files/src/backend/utils/activity/pgstat.c.md) | — | primary implementation |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/pgstat-counter.md` — companion;
  PgStat_Counter type + family structs.
- `knowledge/idioms/checkpoint-coordination.md` — checkpoint
  drives persistence.
- `knowledge/idioms/autovacuum-launcher.md` — autovacuum
  consumes the stats.
- `.claude/skills/debugging/SKILL.md` — pg_stat_* views are
  primary debugging surface.
- `source/src/backend/utils/activity/pgstat.c` — primary
  implementation.
