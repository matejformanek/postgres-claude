# Logical-rep apply — insert/update/delete row handlers

The three DML handlers are how the apply worker replays
publisher-side row events onto local tables.  They share more
than they differ — same locking, same executor-state setup,
same partition-routing fallback, same conflict-reporting path.
The interesting differences live in **how each handler finds
the local tuple** (replica-identity lookup) and what each does
when the lookup fails (conflict types).

This doc covers `apply_handle_insert`, `apply_handle_update`,
`apply_handle_delete`, plus `FindReplTupleInLocalRel` and the
tuple-routing fallback for partitioned targets.  The dispatch
context that calls these is
[[apply-worker-loop-and-dispatch]].  The streaming sub-mode
that may *defer* them to disk is
[[apply-streaming-and-parallel]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/replication/logical/worker.c` — all three handlers
- `source/src/backend/replication/logical/conflict.c` — conflict reporting
- `source/src/backend/replication/logical/relation.c` — `logicalrep_rel_open`, attrmap
- `source/src/backend/replication/logical/proto.c` — wire format readers

## The common shape

All three handlers follow the same skeleton:

```
1. is_skipping_changes() or handle_streamed_transaction(...)?  -> return
2. begin_replication_step()
3. logicalrep_read_{insert,update,delete}(s, ...)
4. rel = logicalrep_rel_open(relid, RowExclusiveLock)
5. should_apply_changes_for_rel(rel)? else release and return
6. SwitchToUntrustedUser if !run_as_owner
7. apply_error_callback_arg.rel = rel
8. create_edata_for_relation
9. slot_store_data(remoteslot, rel, &tup)
10. if partitioned: apply_handle_tuple_routing
    else: apply_handle_*_internal
11. finish_edata
12. RestoreUserContext
13. logicalrep_rel_close
14. end_replication_step
```

The two "internal" functions per op (`*_internal`) are the
actual executor calls — they're called either directly or via
the partition-routing dispatcher.

Three things in this skeleton matter for understanding what
the handlers actually *do*:

### Skipping checks

`worker.c:2666-2668, 2826-2828, 3050-3052` [verified-by-code]:

```c
if (is_skipping_changes() ||
    handle_streamed_transaction(LOGICAL_REP_MSG_INSERT, s))
    return;
```

Two gates that short-circuit the handler:

- **`is_skipping_changes`** — `SUBSCRIPTION ... SKIP (lsn=...)`
  is active; the current transaction's BEGIN-LSN matched the
  skip target.  Every row event in that transaction is silently
  dropped.
- **`handle_streamed_transaction`** — the worker is in
  streaming mode and this message belongs to an in-progress
  stream.  The handler writes the raw bytes to a per-subxact
  spool file and returns; replay happens later at
  STREAM_COMMIT.  See [[apply-streaming-and-parallel]].

### `should_apply_changes_for_rel` — the per-table filter

After opening the relation, the handler checks
`should_apply_changes_for_rel(rel)`.  This returns true if
the relation is in `SUBREL_STATE_READY` (initial sync done) or
`SUBREL_STATE_SYNCDONE`.  Otherwise the change is dropped —
the tablesync worker is still bulk-copying the table and will
also catch up streamed changes itself.

If the filter returns false, the handler releases the lock and
returns.  The comment lines 2676-2679 [from-comment]:

> The relation can't become interesting in the middle of the
> transaction so it's safe to unlock it.

Subscription state is checked at BEGIN; mid-transaction it
can't transition to READY.  That's what makes early lock
release safe.

### Run-as-owner switching

`worker.c:2689-2691` [verified-by-code]:

```c
run_as_owner = MySubscription->runasowner;
if (!run_as_owner)
    SwitchToUntrustedUser(rel->localrel->rd_rel->relowner, &ucxt);
```

`pg_subscription.subrunasowner` toggles between two security
models:

- **`runasowner = false`** (default) — switch to the local
  table's owner before running triggers, default expressions,
  index-expression functions, etc.  This is what makes
  triggers run as the owner that defined them, not as the
  subscription owner.
- **`runasowner = true`** — run everything as the subscription
  owner.  Required for some FDW patterns; sacrifices the
  trigger-as-owner property.

`SwitchToUntrustedUser` (named for the SECURITY DEFINER /
SECURITY INVOKER distinction) is the same primitive triggers
use.  `RestoreUserContext` happens in the cleanup tail of the
handler.

## INSERT — `apply_handle_insert`

`worker.c:2650-2733` [verified-by-code].  The handler reads
one row's data and inserts it via `ExecSimpleRelationInsert`.

### Reading the row

`worker.c:2672` [verified-by-code]:

```c
relid = logicalrep_read_insert(s, &newtup);
```

`logicalrep_read_insert` (in `proto.c`) returns the publisher-
side relation OID — translated to the local OID through the
relation-map cache in `logicalrep_rel_open`.  The
`LogicalRepTupleData newtup` carries:

- `ncols` — number of columns in the publisher's row
- `colvalues[]` — per-column text values
- `colstatus[]` — per-column status flags (UNCHANGED, TOASTED,
  TEXT)

`colstatus` is the key for understanding **what's actually
sent on the wire**.  Three values matter:

| Status | Meaning |
|---|---|
| `LOGICALREP_COLUMN_TEXT` | a value follows |
| `LOGICALREP_COLUMN_NULL` | this column is NULL |
| `LOGICALREP_COLUMN_UNCHANGED` | (UPDATE only) value unchanged, omitted from message |
| `LOGICALREP_COLUMN_TOASTED` | (UPDATE only) value is unchanged-TOAST; refers to local row |

### Filling the slot

`worker.c:2703-2707` [verified-by-code]:

```c
oldctx = MemoryContextSwitchTo(GetPerTupleMemoryContext(estate));
slot_store_data(remoteslot, rel, &newtup);
slot_fill_defaults(rel, estate, remoteslot);
MemoryContextSwitchTo(oldctx);
```

`slot_store_data` walks the **attrmap** — the
publisher-column→local-column mapping computed by
`logicalrep_relmap_build_attrmap` — and parses each value's
text form via the local type's input function.  Local-only
columns get NULL.

`slot_fill_defaults` is the **subscriber-only DEFAULT
substitution** — for local columns that have a `DEFAULT`
expression AND are not provided by the publisher, evaluate the
default expression now.  This is what makes `INSERT INTO
... (a) VALUES (1)` work when the subscriber side has
`b SERIAL` not on the publisher.

### Partition routing or direct insert

`worker.c:2709-2720` [verified-by-code]:

```c
if (rel->localrel->rd_rel->relkind == RELKIND_PARTITIONED_TABLE)
    apply_handle_tuple_routing(edata,
                               remoteslot, NULL, CMD_INSERT);
else
{
    ResultRelInfo *relinfo = edata->targetRelInfo;
    ExecOpenIndices(relinfo, false);
    apply_handle_insert_internal(edata, relinfo, remoteslot);
    ExecCloseIndices(relinfo);
}
```

Partitioned local tables go through `apply_handle_tuple_routing`
— see §Partition routing below.  Regular tables go through
`apply_handle_insert_internal`:

```c
/* worker.c:2740-2759 */
static void
apply_handle_insert_internal(ApplyExecutionData *edata,
                             ResultRelInfo *relinfo,
                             TupleTableSlot *remoteslot)
{
    ...
    InitConflictIndexes(relinfo);
    TargetPrivilegesCheck(relinfo->ri_RelationDesc, ACL_INSERT);
    ExecSimpleRelationInsert(relinfo, estate, remoteslot);
}
```

`InitConflictIndexes` is the call that flags "this insert
could conflict on a unique index" — used by conflict reporting
to know which index produced the violation.

`ExecSimpleRelationInsert` is the simplest path through the
executor — no plan tree, no triggers-via-ExecInsert, just
heap-AM `tuple_insert` + index inserts + AFTER-INSERT triggers.

## UPDATE — `apply_handle_update`

`worker.c:2806-2921` [verified-by-code].  Two extra concerns
versus INSERT:

### 1. Updatability check

`worker.c:2849-2850` [verified-by-code]:

```c
/* Check if we can do the update. */
check_relation_updatable(rel);
```

`check_relation_updatable` at `worker.c:2765-2799`
[verified-by-code] enforces the **replica-identity
requirement**:

```c
if (rel->updatable)
    return;

if (OidIsValid(GetRelationIdentityOrPK(rel->localrel)))
{
    ereport(ERROR, ...
            "publisher did not send replica identity column "
            "expected by the logical replication target relation");
}

ereport(ERROR, ...
        "logical replication target relation has "
        "neither REPLICA IDENTITY index nor PRIMARY KEY and "
        "published relation does not have REPLICA IDENTITY FULL");
```

Two error modes:

- **subscriber has PK/RI but publisher didn't include it** —
  the publisher must send the key columns of the local PK/RI
  even if the publisher's PK is different.
- **subscriber has no PK/RI** — the only way to find a row is
  REPLICA IDENTITY FULL (send every column for comparison),
  which the publisher must have configured.

These are publisher-side configuration problems but the apply
worker is the one that catches them at runtime.

### 2. updatedCols tracking

`worker.c:2867-2894` [verified-by-code]:

```c
target_perminfo = list_nth(estate->es_rteperminfos, 0);
for (int i = 0; i < remoteslot->tts_tupleDescriptor->natts; i++)
{
    CompactAttribute *att = TupleDescCompactAttr(remoteslot->tts_tupleDescriptor, i);
    int remoteattnum = rel->attrmap->attnums[i];

    if (!att->attisdropped && remoteattnum >= 0)
    {
        if (newtup.colstatus[remoteattnum] != LOGICALREP_COLUMN_UNCHANGED)
            target_perminfo->updatedCols =
                bms_add_member(target_perminfo->updatedCols,
                               i + 1 - FirstLowInvalidHeapAttributeNumber);
    }
}
```

The comment at lines 2867-2874 [from-comment]:

> Populate updatedCols so that per-column triggers can fire,
> and so executor can correctly pass down indexUnchanged hint.

`updatedCols` is the bitmap of column attnums the executor
needs to know "this was actually changed".  Two consumers:

- **Per-column triggers** (`WHEN UPDATE OF col`) need to fire
  only when their column is in the set.
- **Index updates** can be skipped when none of the indexed
  columns are in the set (the HOT path).

The check `colstatus != LOGICALREP_COLUMN_UNCHANGED` is the
key — if the publisher didn't send a value because the column
wasn't modified, we don't mark it as updated locally either.

### 3. Find-then-update

`apply_handle_update_internal` at `worker.c:2929-3026`
[verified-by-code] does the local lookup:

```c
found = FindReplTupleInLocalRel(edata, localrel,
                                &relmapentry->remoterel,
                                localindexoid,
                                remoteslot, &localslot);

if (found)
{
    /* possibly report cross-origin conflict */
    if (GetTupleTransactionInfo(localslot, ...) &&
        conflicttuple.origin != replorigin_xact_state.origin)
    {
        ReportApplyConflict(estate, relinfo, LOG, CT_UPDATE_ORIGIN_DIFFERS,
                            remoteslot, newslot, list_make1(&conflicttuple));
    }

    /* Process and store remote tuple in the slot */
    slot_modify_data(remoteslot, localslot, relmapentry, newtup);

    EvalPlanQualSetSlot(&epqstate, remoteslot);
    InitConflictIndexes(relinfo);
    TargetPrivilegesCheck(relinfo->ri_RelationDesc, ACL_UPDATE);
    ExecSimpleRelationUpdate(relinfo, estate, &epqstate, localslot,
                             remoteslot);
}
else
{
    /* Not-found path — report CT_UPDATE_MISSING or CT_UPDATE_DELETED */
}
```

Three things:

#### `slot_modify_data` — merge old + new

`slot_modify_data` (in `proto.c`) starts from `localslot`'s
current values and overwrites only the columns marked
`LOGICALREP_COLUMN_TEXT` in `newtup`.  Columns marked
`UNCHANGED` keep their local values; columns marked `TOASTED`
also keep their local values (the TOAST pointer wasn't
re-shipped).

This is what makes "UPDATE with unchanged-TOAST" cheap on the
wire — the row's text columns aren't re-sent when they
weren't modified.

#### `EvalPlanQualSetSlot` — for index recheck

The `epqstate` is initialized at line 2944 and used here to
hold the new tuple for any EPQ-driven index rechecks.  The
`ExecSimpleRelationUpdate` machinery uses EPQ to handle
concurrent updates (someone else updated the row between our
FindReplTuple and our ExecUpdate).

#### Cross-origin conflict detection

Lines 2963-2978 [verified-by-code]:

```c
if (GetTupleTransactionInfo(localslot, &conflicttuple.xmin,
                            &conflicttuple.origin, &conflicttuple.ts) &&
    conflicttuple.origin != replorigin_xact_state.origin)
{
    ...
    ReportApplyConflict(estate, relinfo, LOG, CT_UPDATE_ORIGIN_DIFFERS, ...);
}
```

The local row's t_xmin is checked against the replication
origin map (`pg_replication_origin_status`).  If the row was
last touched by a *different* origin (e.g. another
subscription, or a local writer), this is a **cross-origin
conflict** — logged but not blocked.

The conflict is reported with type `CT_UPDATE_ORIGIN_DIFFERS`;
the apply still happens (last-writer-wins on the local side).
For deterministic conflict resolution see the
`conflict_resolver` infrastructure (out of scope for this doc).

### 4. Not-found: missing vs deleted

`worker.c:2994-3021` [verified-by-code]:

```c
else
{
    ConflictType type;

    if (FindDeletedTupleInLocalRel(localrel, localindexoid, remoteslot,
                                   &conflicttuple.xmin,
                                   &conflicttuple.origin,
                                   &conflicttuple.ts) &&
        conflicttuple.origin != replorigin_xact_state.origin)
        type = CT_UPDATE_DELETED;
    else
        type = CT_UPDATE_MISSING;

    slot_store_data(newslot, relmapentry, newtup);
    ReportApplyConflict(estate, relinfo, LOG, type, remoteslot, newslot,
                        list_make1(&conflicttuple));
}
```

`FindDeletedTupleInLocalRel` (`worker.c:612`) checks the
relation's dead-tuple slots for a recently-deleted match.  If
found and from a different origin, the conflict is
`CT_UPDATE_DELETED`; otherwise `CT_UPDATE_MISSING`.

The comment at line 3000-3002 [from-comment]:

> Detecting whether the tuple was recently deleted or never
> existed is crucial to avoid misleading the user during
> conflict handling.

This is the diagnostics that lets users decide between "fix
the publisher" (UPDATE_MISSING — the row was never replicated)
and "accept the divergence" (UPDATE_DELETED — concurrent
delete on subscriber).

## DELETE — `apply_handle_delete`

`worker.c:3034-3120` [verified-by-code] is structurally
identical to UPDATE but simpler:

- Reads only `oldtup` (the REPLICA IDENTITY columns).
- Calls `slot_store_data(remoteslot, rel, &oldtup)` to build
  the search tuple.
- Calls `apply_handle_delete_internal` which does
  `FindReplTupleInLocalRel` + `ExecSimpleRelationDelete`.

The not-found case reports `CT_DELETE_MISSING` (after
`FindDeletedTupleInLocalRel` check distinguishes from
`CT_DELETE_ORIGIN_DIFFERS`).

DELETE has no `updatedCols` tracking and no `slot_modify_data`
— it doesn't need them.

## `FindReplTupleInLocalRel` — replica-identity lookup

`worker.c:607` (declaration), implementation later in the
file.  Returns true if a matching local tuple was found,
filling `*localslot` with it.

Three lookup strategies, picked at `logicalrep_rel_open` time
into `rel->localindexoid`:

1. **Index scan** — when the local table has a usable index
   over the REPLICA IDENTITY columns.  The function uses
   `index_beginscan` + `index_getnext_slot` to find the row.
2. **Seq scan** — when REPLICA IDENTITY is FULL and the
   subscriber has no matching index.  The function walks the
   whole table comparing every row.  This is what makes
   replicating large tables with no PK extremely slow.
3. **Single TID scan** — for partitioned tables, when a
   specific partition is targeted.

The `localindexoid` field on `LogicalRepRelMapEntry` is what
gets passed in; the caller (`apply_handle_update_internal` /
`apply_handle_delete_internal`) reads it from
`rel->localindexoid`.

Key behavior: the comparison uses the **REPLICA IDENTITY
column subset** of the search tuple.  Columns outside the
replica identity are ignored.  This is what makes REPLICA
IDENTITY DEFAULT (just the PK) work without needing every
column.

## Partition routing — `apply_handle_tuple_routing`

`worker.c:618` declares the function; lines around 3400-3550
implement it [referenced in the dispatch at 2710-2712 and
3096-3097].

The fallback path for partitioned targets.  Three steps:

1. **Choose the partition.**  `ExecFindPartition` runs the
   parent's partition routing on the new tuple.
2. **Convert the tuple to the partition's tuple descriptor.**
   The partition may have different column order, dropped
   columns, etc.  `ConvertTupleToSlot` reformats.
3. **Recurse into the per-partition handler.**  For INSERT,
   call `apply_handle_insert_internal` with the partition's
   `ResultRelInfo`.  For UPDATE, this is more complex: if the
   partition changes due to UPDATE-of-key, the function does
   `apply_handle_delete_internal` on the old partition then
   `apply_handle_insert_internal` on the new one — see lines
   3455-3460.

The "INSERT-after-DELETE-because-partition-changed" path is
the source of subtle bugs: AFTER triggers fire as if it were
a real DELETE then a real INSERT, not as an UPDATE.

## Conflict reporting — `ReportApplyConflict`

`conflict.c` houses the conflict-reporting machinery.
`ReportApplyConflict` builds a `pg_logical_replication_conflict`-
format error message and dispatches it through
`ereport(LOG, ...)`.  The message includes:

- conflict type (one of `CT_*` constants)
- local row's xmin / origin / timestamp
- remote row's values
- the originating subscription name

Output ends up in the server log; the conflict is **logged
but not blocked** for ORIGIN_DIFFERS variants and
UPDATE/DELETE missing — the apply silently continues.

For UNIQUE / PRIMARY KEY violations, the conflict path is
different: the executor throws the underlying error and the
apply worker's normal error handling catches it, logs, and
either re-tries (if configured) or restarts.

## Invariants worth remembering

1. **`is_skipping_changes()` and
   `handle_streamed_transaction(...)` are the two short-
   circuits at the top of every handler.**
2. **`logicalrep_rel_open` returns a cached
   `LogicalRepRelMapEntry`** keyed by publisher's relid; the
   attrmap converts publisher to local column attnums.
3. **`SUBREL_STATE_READY` / `SYNCDONE` is the only state in
   which row changes are applied.**  Anything else gets
   dropped silently (the tablesync worker will catch up).
4. **`runasowner = false` (default) switches to the local
   table owner per row.**  Triggers fire as the owner.
5. **REPLICA IDENTITY is the search key for UPDATE and
   DELETE.**  No replica identity ⇒ runtime error.
6. **UPDATE's `updatedCols` skips
   `LOGICALREP_COLUMN_UNCHANGED` columns.**  This is what
   keeps per-column triggers correct.
7. **`slot_modify_data` preserves local values for UNCHANGED
   and TOASTED columns.**  Wire format never re-ships
   unmodified TOAST.
8. **Cross-origin conflicts are logged, not blocked.**
   `CT_UPDATE_ORIGIN_DIFFERS`, `CT_DELETE_ORIGIN_DIFFERS`.
9. **Missing-tuple conflict distinguishes
   recently-deleted vs never-existed.**  `CT_UPDATE_DELETED`
   vs `CT_UPDATE_MISSING`.
10. **Partition routing recurses into the per-partition
    `*_internal` function.**  UPDATE that changes partition
    becomes DELETE-then-INSERT, with separate trigger firings.

## Useful greps

```bash
# The three handlers
grep -n "^apply_handle_insert\|^apply_handle_update\|^apply_handle_delete" \
    source/src/backend/replication/logical/worker.c

# Internal workhorses
grep -n "apply_handle_insert_internal\|apply_handle_update_internal\|apply_handle_delete_internal" \
    source/src/backend/replication/logical/worker.c

# Replica identity lookup
grep -n "FindReplTupleInLocalRel\|FindDeletedTupleInLocalRel\|localindexoid" \
    source/src/backend/replication/logical/worker.c

# Conflict types
grep -rn "CT_INSERT_EXISTS\|CT_UPDATE_ORIGIN_DIFFERS\|CT_UPDATE_MISSING\|CT_UPDATE_DELETED\|CT_DELETE_ORIGIN_DIFFERS\|CT_DELETE_MISSING" \
    source/src/include/replication/conflict.h

# Tuple routing
grep -n "apply_handle_tuple_routing\|ExecFindPartition" \
    source/src/backend/replication/logical/worker.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/conflict.c`](../files/src/backend/replication/logical/conflict.c.md) | — | conflict reporting |
| [`src/backend/replication/logical/proto.c`](../files/src/backend/replication/logical/proto.c.md) | — | wire format readers |
| [`src/backend/replication/logical/relation.c`](../files/src/backend/replication/logical/relation.c.md) | — | logicalrep_rel_open, attrmap |
| [`src/backend/replication/logical/worker.c`](../files/src/backend/replication/logical/worker.c.md) | — | all three handlers |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-replication-message`](../scenarios/add-new-replication-message.md)

<!-- /scenarios:auto -->

## Cross-references

- [[apply-worker-loop-and-dispatch]] — calls these handlers
  via `apply_dispatch`.
- [[apply-streaming-and-parallel]] — `handle_streamed_transaction`
  forks streaming rows into spool files.
- [[heap-tuple-visibility-mvcc]] — `ExecSimpleRelationUpdate`
  uses MVCC to handle concurrent writes; EPQ recheck path.
- [[evalplanqual-recheck]] — `EvalPlanQualInit`/`SetSlot`/`End`
  used in the update handler.
- [[fk-trigger-ri]] — apply respects local FK triggers; some
  conflict types fire FK actions.
- [[catalog-conventions]] — `pg_subscription_rel.srsubstate`
  is the SUBREL_STATE machine.
- [[buffer-manager]] — `ExecSimpleRelationInsert` /
  `ExecSimpleRelationUpdate` ultimately go through the
  buffer manager.
