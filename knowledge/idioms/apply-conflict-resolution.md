# Apply conflict resolution — handling INSERT-exists, UPDATE-missing, etc.

When the apply worker tries to replay a remote
INSERT/UPDATE/DELETE on the subscriber, the local state may
not match what the publisher expects. The 8-value
`ConflictType` enum classifies the resulting conflict, and
`ReportApplyConflict` emits a structured log message with the
local + remote tuples so the operator can diagnose and decide.
The apply worker's default behavior is to ERROR out
(`elevel=ERROR`), halting the apply worker until the operator
intervenes.

Anchors:
- `source/src/include/replication/conflict.h:30-62` —
  ConflictType enum [verified-by-code]
- `source/src/backend/replication/logical/conflict.c:105` —
  ReportApplyConflict [verified-by-code]
- `knowledge/idioms/apply-worker-loop.md` — companion
- `knowledge/idioms/replication-origin-tracking.md` —
  companion (origin_id classifies ORIGIN_DIFFERS conflicts)
- `.claude/skills/replication-overview/SKILL.md` — companion

## The 8 conflict types

[verified-by-code `conflict.h:30-62`]

```c
typedef enum
{
    CT_INSERT_EXISTS,             /* unique-constraint hit on insert */
    CT_UPDATE_ORIGIN_DIFFERS,     /* row modified by different origin */
    CT_UPDATE_EXISTS,             /* updated value hits unique constraint */
    CT_UPDATE_DELETED,            /* row was concurrently deleted */
    CT_UPDATE_MISSING,            /* target row not found */
    CT_DELETE_ORIGIN_DIFFERS,     /* deletion target modified by other origin */
    CT_DELETE_MISSING,            /* delete target not found */
    CT_MULTIPLE_UNIQUE_CONFLICTS, /* multiple unique constraints hit */
} ConflictType;
```

Each conflict type has a specific local-state recognition rule
and a logged description.

## The "missing" conflicts

- **CT_UPDATE_MISSING** — apply tries to UPDATE a row by
  primary key; no such row exists locally. Could be:
  - The row was deleted locally (by another origin or a local
    DELETE).
  - The row was never replicated (subscription lag or
    skip-LSN).
- **CT_DELETE_MISSING** — similar for DELETE.

Common cause: a local DELETE removed a row before the remote
update arrived. Default response: ERROR; alternative:
`subscription ... DISABLE ON ERROR` skips it.

## The "exists" conflicts

- **CT_INSERT_EXISTS** — apply tries INSERT but a row with
  the same primary key (or unique key) exists locally.
- **CT_UPDATE_EXISTS** — apply UPDATE would put the row into
  a state that violates a unique constraint.

Common cause: local INSERT happened first, or two publishers
inserted to the same key.

## The "origin differs" conflicts

[from-comment + use of `origin_id`]

- **CT_UPDATE_ORIGIN_DIFFERS** — the row being updated has
  `xmin` from a different origin than expected.
- **CT_DELETE_ORIGIN_DIFFERS** — same for delete.

This is the **subtle** conflict: the row exists, the key
matches, but it was last modified by a DIFFERENT origin. Could
be:
- Bidirectional replication where the other direction's
  change arrived first.
- A local UPDATE between when the publisher saw the row and
  when its update arrived.

Default response: ERROR (preserve the foreign change).

## ReportApplyConflict — the structured log emit

[verified-by-code `conflict.c:105`]

```c
void
ReportApplyConflict(EState *estate, ResultRelInfo *relinfo,
                    int elevel, ConflictType type, ...);
```

Emits via `ereport(elevel, ...)` with:
- The conflict type (descriptive name).
- The local tuple's column values (for keys + commonly
  selected columns).
- The remote tuple's column values.
- The origin id and remote LSN.
- A pointer to relevant documentation.

`elevel` is typically `ERROR`, halting the apply worker. For
auto-skip-on-error mode (`subscription...disable_on_error =
true`), the worker logs at ERROR then disables itself.

## Recovery operations

After a conflict halts the worker:

```sql
-- Option 1: skip the offending xact via LSN
ALTER SUBSCRIPTION s SKIP (lsn = '0/12345');

-- Option 2: disable + reenable to retry
ALTER SUBSCRIPTION s DISABLE;
-- ... resolve underlying issue ...
ALTER SUBSCRIPTION s ENABLE;

-- Option 3: manually apply the change + advance origin LSN
SELECT pg_replication_origin_session_advance(
    'pg_<subid>', '0/12345');
```

The choice depends on whether the conflict represents real
divergence (skip if intentional) or transient state (re-enable
after the publisher's data settles).

## pg_stat_subscription_stats

[from `conflict.h:23-28`]

> This enum is used in statistics collection (see
> PgStat_StatSubEntry::conflict_count ...) as well, therefore,
> when adding new values or reordering existing ones, ensure to
> review and potentially adjust the corresponding statistics
> collection codes.

Conflict counts are tracked per-subscription in pgstats. Query
via:

```sql
SELECT subid, conflict_count_array
FROM pg_stat_subscription_stats;
```

Lets monitoring observe conflict frequency without parsing
logs.

## ConflictTupleInfo — the recorded shape

```c
typedef struct ConflictTupleInfo
{
    /* tuple slot containing the conflicting local row */
    TupleTableSlot *slot;
    /* origin id of last modifier */
    RepOriginId origin;
    /* xmin of conflicting tuple */
    TransactionId xmin;
} ConflictTupleInfo;
```

Held by ReportApplyConflict for the log emit; tuple data is
materialized into the error message via slot deformation.

## CT_MULTIPLE_UNIQUE_CONFLICTS

Special case: one INSERT or UPDATE hits MULTIPLE unique
constraints simultaneously. The conflict log enumerates each
violation.

## Operator playbook

| Conflict | Common cause | Resolution |
|---|---|---|
| INSERT_EXISTS | Dual-write to same key | Skip xact; investigate; consider conflict-detection trigger |
| UPDATE_MISSING | Local DELETE before remote UPDATE arrived | Skip xact; replay missing data |
| UPDATE_ORIGIN_DIFFERS | Bidirectional rep conflict | Pick winner manually; advance origin |
| DELETE_MISSING | Already deleted | Skip xact |
| CT_MULTIPLE | Complex insert | Review key uniqueness across origins |

## Common review-time concerns

- **Default ERROR halts worker** — design subscriptions with
  `disable_on_error` if catastrophic stalls are unacceptable.
- **SKIP LSN is per-subscription** — won't help with future
  conflicts.
- **Bidirectional rep needs origin-aware conflict policy** —
  filter_by_origin_cb + skip rules.
- **EXCLUDE constraints aren't covered** — only unique +
  primary key.
- **Conflict stats in pgstats** — monitor + alert on conflict
  spikes.

## Invariants

- **[INV-1]** 8 ConflictTypes covering INSERT / UPDATE /
  DELETE × (missing / exists / origin-differs).
- **[INV-2]** Default elevel = ERROR halts apply worker.
- **[INV-3]** Conflict log includes local + remote tuples +
  origin_id.
- **[INV-4]** SKIP LSN / DISABLE+ENABLE / manual advance —
  three recovery paths.
- **[INV-5]** Conflict counts tracked per-subscription in
  pgstats.

## Useful greps

- The conflict types:
  `grep -n 'CT_INSERT_EXISTS\|CT_UPDATE_\|CT_DELETE_\|ConflictType' source/src/include/replication/conflict.h | head -15`
- ReportApplyConflict:
  `grep -n 'ReportApplyConflict' source/src/backend/replication/logical/conflict.c | head -5`
- Conflict-detection callers:
  `grep -RIn 'ReportApplyConflict' source/src/backend/replication/logical | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/conflict.c`](../files/src/backend/replication/logical/conflict.c.md) | 105 | ReportApplyConflict |
| [`src/backend/replication/logical/conflict.c`](../files/src/backend/replication/logical/conflict.c.md) | — | full module |
| [`src/include/replication/conflict.h`](../files/src/include/replication/conflict.h.md) | 30 | ConflictType enum |
| [`src/include/replication/conflict.h`](../files/src/include/replication/conflict.h.md) | — | ConflictType + structs |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/apply-worker-loop.md` — companion;
  apply path that hits conflicts.
- `knowledge/idioms/replication-origin-tracking.md` —
  origin_id classifies ORIGIN_DIFFERS.
- `knowledge/idioms/tablesync-initial-copy.md` —
  conflicts can occur during catchup.
- `knowledge/idioms/pgstat-flush-timing.md` — conflict
  stats flushed via pgstat.
- `knowledge/data-structures/tupletableslot.md` —
  ConflictTupleInfo wraps a slot.
- `knowledge/subsystems/replication.md` — replication.
- `.claude/skills/replication-overview/SKILL.md` — companion.
- `source/src/backend/replication/logical/conflict.c` —
  full module.
- `source/src/include/replication/conflict.h` —
  ConflictType + structs.
