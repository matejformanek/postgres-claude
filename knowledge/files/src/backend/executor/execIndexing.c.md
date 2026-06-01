# execIndexing.c

- **Source:** `source/src/backend/executor/execIndexing.c` (1189 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (entry points; concurrency narrative in header)

## Purpose

After a heap row has been inserted/updated, push the index entries and enforce
**unique** and **exclusion** constraints. ModifyTable calls in here.
The file header is a long, important essay on PG's "speculative-insert"
protocol for ON CONFLICT and the race between two concurrent inserters.
[from-comment] `:3-115`

## Two main entry points

### `ExecInsertIndexTuples(resultRelInfo, slot, estate, update, noDupErr, &specConflict, arbiterIndexes, onlySummarizing)` `:311`

Inserts the row into every index of the result relation:

- Iterates `resultRelInfo->ri_IndexRelationDescs` / `ri_IndexRelationInfo`.
- For partial indexes, runs the predicate ExprState (cached on
  IndexInfo->ii_PredicateState) and skips when false.
- For each, calls `index_insert` with an appropriate `IndexUniqueCheck`:
  - `UNIQUE_CHECK_YES` for normal unique,
  - `UNIQUE_CHECK_PARTIAL` for deferrable unique (returns conflict but does
    not error; caller queues a recheck),
  - `UNIQUE_CHECK_NO` for non-unique.
- For **speculative** inserts (ON CONFLICT path), `noDupErr=true`: any
  detected conflict in a unique arbiter index returns `*specConflict=true`
  and the caller (`nodeModifyTable`) then `heap_abort_speculative`s the
  heap row, waits for the conflicting xact, and retries.
- Exclusion constraints are not checked in this call (they need a separate
  scan, see below); the function records them and runs them after.

Return value is a list of OIDs of indexes with pending conflicts (deferred
unique or exclusion).

### `ExecCheckIndexConstraints(resultRelInfo, slot, estate, &conflictTid, arbiterIndexes)` `:543`

The **dry-run** half of speculative insert: probes the listed arbiter
indexes without inserting, and reports back the CTID of a conflicting row
(or InvalidItemPointer) for ON CONFLICT … DO UPDATE to fetch and lock.
This runs *before* the heap insert.

## Exclusion constraint enforcement

`check_exclusion_or_unique_constraint(heap, index, indexInfo, tupleid,
values, isnull, estate, newIndex, waitMode, violationOK, conflictTid)` `:705`

For each tuple already in the index that *might* violate (range from the
index search), call the exclusion operator. If conflict and:

- `waitMode=CEOUC_WAIT` → wait for the other xact and retry;
- `waitMode=CEOUC_NOWAIT` → throw error;
- `waitMode=CEOUC_LIVELOCK_PREVENTING_WAIT` → wait, but if the conflicting
  tuple is from our own xact (uncommitted), this implements the
  "don't conflict with myself" rule.

If `violationOK`, the caller wanted to know about it (deferred-unique
recheck or speculative insert) and we report via conflictTid.

## Why this code is famously subtle

- Two backends inserting the same key into a deferrable unique index must
  both notice; deferred check runs at constraint-check time.
- ON CONFLICT must atomically reserve a slot via `heap_insert(SPECULATIVE)`
  before the index lookup; if any arbiter sees a conflict, we
  `heap_abort_speculative` (which super-deletes the tuple) so other waiters
  see no row. This is what the file header §"Speculative Insertion"
  describes.

## `index_recheck_constraint` `:988`

For DEFERRED unique constraint check at commit time: rescan a previously
flagged tuple's keys, ensure no live row violates. Called from the trigger
machinery.

## Tags

- [verified-by-code] entry points, IndexUniqueCheck values, waitMode enum.
- [from-comment] speculative-insert protocol narrative (file header).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
