# Xmin horizon management — VACUUM's freedom boundary

The "oldest xmin" is the central concept controlling which dead
tuples VACUUM can remove. A tuple deleted by transaction
`xmax = T` can only be physically removed once **NO active
transaction's snapshot still considers T to be in the future** —
i.e., the global oldest-xmin has moved past T. This single
horizon governs VACUUM cleanup, HOT prune, predicate-lock GC,
and SLRU truncation. Long-running transactions hold the horizon
back; the result is "VACUUM ran but nothing got cleaned."

Anchors:
- `source/src/include/storage/procarray.h` — `GetOldestNonRemovableTransactionId`
  [verified-by-code]
- `source/src/backend/storage/ipc/procarray.c` — implementation
- `knowledge/idioms/snapshot-acquisition.md` — snapshot
  acquisition affects xmin via active-snapshot stack
- `knowledge/subsystems/access-heap.md` — heap VACUUM

## The function

```c
extern TransactionId GetOldestNonRemovableTransactionId(Relation rel);
```

[verified-by-code `procarray.h:53`]

Returns the **oldest xmin** that any currently-active
transaction in this cluster might still consider visible. A
tuple's xmax must be **strictly less than** this value for the
tuple to be removable.

The `rel` parameter modulates the answer:
- For a regular relation, the global oldest xmin.
- For a system catalog, may be more conservative (catalogs are
  read by many backends; horizon must respect all snapshots).
- For a temp relation, owned backend's xmin only.

## What contributes to the horizon

Every PGPROC entry advertises an `xmin` slot in shared memory.
The xmin is the snapshot's xmin — the oldest XID this backend
"can still see." Backends update their xmin every time they
acquire a snapshot.

A backend with NO snapshot active advertises `InvalidTransactionId`
(0); it doesn't pin the horizon.

The cluster oldest xmin is the **min over all live PGPROCs'
advertised xmins**. If even one backend has an old snapshot,
the horizon is held back.

## The classic causes of "stuck horizon"

1. **Long-running transaction** — common case. The transaction
   has held a snapshot for hours; its xmin advertises an old
   value. Solution: kill the transaction or let it commit.
2. **Replication slot with old `xmin` / `catalog_xmin`** —
   logical-replication slots advertise their own xmin to
   prevent the publisher from removing rows the subscriber
   hasn't replicated yet. Inactive slots are a frequent
   source of horizon drift.
3. **Idle-in-transaction sessions** — connections that ran
   `BEGIN` and then went idle (waiting for client input) hold
   the snapshot they acquired. The `idle_in_transaction_session_timeout`
   GUC is the defense.
4. **Standby's `hot_standby_feedback = on`** — the standby
   reports its oldest snapshot to the primary, pinning the
   primary's horizon. Useful for query-stability but a
   bloat hazard if the standby is busy.

## The procarray scan

`GetOldestNonRemovableTransactionId` walks the ProcArray
(every PGPROC), checks each backend's advertised xmin, and
returns the minimum. The scan takes `ProcArrayLock` shared.

On busy systems this is a hot lock — every snapshot
acquisition takes ProcArrayLock-shared, every commit takes it
exclusive. The lock-free snapshot fast path (PG 14+)
substantially reduced contention.

## The horizon-aware downstream consumers

| Consumer | Behavior |
|---|---|
| Heap VACUUM | Removes tuples whose xmax < horizon |
| HOT prune | Removes intermediate chain members whose xmax < horizon |
| pg_subtrans truncation | Removes subxact entries < horizon |
| pg_multixact truncation | Removes MultiXact entries < horizon |
| Predicate-lock GC | Removes locks held by transactions < horizon |
| SLRU truncation | Various SLRUs trim past horizon |

The horizon is consulted at every cleanup decision. A stuck
horizon = bloat across all of these.

## GlobalVisHorizonKindForRel

[verified-by-code `procarray.h` via `GlobalVis*` accessor family]

Modern VACUUM doesn't call `GetOldestNonRemovableTransactionId`
in the inner loop — it uses `GlobalVisHorizonKindForRel` to
pick the right horizon family, then `GlobalVisTestFor*` to do
quick "is this XID still visible?" tests against a cached
snapshot.

The split exists for performance: the horizon doesn't change
mid-VACUUM, so cache it once and re-test cheaply per tuple.

## The horizon "kinds"

- **`GLOBALVIS_SHARED_RELS`** — for shared catalogs
  (`pg_database`, `pg_authid`); horizon must respect every
  database's snapshots.
- **`GLOBALVIS_CATALOG_RELS`** — per-database catalogs.
- **`GLOBALVIS_DATA_RELS`** — user tables; the loosest
  horizon (replication-slot xmin doesn't typically apply).
- **`GLOBALVIS_TEMP_RELS`** — temp tables; only owning
  backend's snapshot matters.

The temp horizon being backend-local is why VACUUM on a temp
table never has the "stuck horizon" problem — there's only
one backend that could pin it.

## Diagnosing "VACUUM ran but nothing got cleaned"

The standard diagnostic sequence:

1. `SELECT pid, xact_start, state, query FROM pg_stat_activity
   WHERE xact_start IS NOT NULL ORDER BY xact_start;`
   — find long-running transactions.
2. `SELECT slot_name, xmin, catalog_xmin FROM
   pg_replication_slots;` — find slots pinning the horizon.
3. `SELECT pid, application_name, backend_xmin FROM
   pg_stat_replication;` — check standby feedback.

The transaction / slot with the oldest xmin is the
bloat-causer. Fix it before re-VACUUM.

## Common review-time concerns

- **Don't hold an old snapshot across IO that may take
  minutes.** The snapshot advertises xmin; horizon stuck.
- **Replication-slot xmin pinning is durable.** A dropped or
  inactive slot still pins the horizon until ALTER
  REPLICATION_SLOT advances or DROP removes.
- **VACUUM never advances the horizon.** It only consumes it.
  Horizon advance requires snapshots to be released.
- **Custom code that allocates a snapshot must release it.**
  Forgetting = permanent xmin-pin until backend exit.

## Invariants

- **[INV-1]** A tuple's xmax < horizon ⇒ removable.
- **[INV-2]** Horizon = min over all live PGPROCs' advertised
  xmin (+ replication-slot xmins where relevant).
- **[INV-3]** Long-running transactions pin the horizon.
- **[INV-4]** Per-relation kind selects the right horizon
  family (shared / catalog / data / temp).
- **[INV-5]** VACUUM caches the horizon at start; doesn't
  re-query per tuple.

## Useful greps

- The horizon API:
  `grep -RIn 'GetOldestNonRemovableTransactionId\|GlobalVis' source/src/include/storage/procarray.h`
- All consumers:
  `grep -RIn 'GetOldestNonRemovableTransactionId' source/src/backend | head -20`
- Replication-slot xmin pinning:
  `grep -n 'ReplicationSlotsComputeRequiredXmin' source/src/backend/replication/slot.c`

## Cross-references

- `knowledge/idioms/snapshot-acquisition.md` — snapshot acq
  advertises the xmin that pins the horizon.
- `knowledge/data-structures/snapshot-lifecycle.md` — Snapshot
  struct + xmin field.
- `knowledge/data-structures/pgproc-fields.md` — the advertised
  `xmin` field on each PGPROC.
- `knowledge/idioms/vacuum-skip-pages.md` — companion; VACUUM
  page-skipping logic consumes the horizon.
- `.claude/skills/debugging/SKILL.md` — "VACUUM ran but
  nothing was cleaned" is a canonical diagnostic.
- `knowledge/subsystems/replication.md` — replication slots
  pin the horizon via `catalog_xmin`.
- `source/src/include/storage/procarray.h` — the API.
- `source/src/backend/storage/ipc/procarray.c` —
  implementation.
