# TableAm vtable lifecycle — the table-access-method API

Like `IndexAmRoutine` for indexes, `TableAmRoutine` is the
vtable every **table access method** (heap, custom storage
engines) implements. Heap is the only in-tree table AM, but
the interface exists so extensions can plug in alternative
storage (columnar, append-only, encrypted-at-rest, etc.).
The executor consumes tuples through this vtable; the AM
decides what's on disk and how to scan it.

Anchors:
- `source/src/include/access/tableam.h:321-700` —
  `TableAmRoutine` struct [verified-by-code]
- `source/src/backend/access/heap/heapam_handler.c` —
  heap AM impl
- `knowledge/data-structures/indexamroutine.md` — companion
  index-AM vtable
- `knowledge/subsystems/access-heap.md` — the heap AM

## The struct (~60 function pointers)

[verified-by-code `tableam.h:321-700`]

Categories of callbacks:

1. **Slot lifecycle** — `slot_callbacks` returns the right
   `TupleTableSlotOps` for this AM's storage form.
2. **Scan management** — `scan_begin`, `scan_end`,
   `scan_rescan`, `scan_getnextslot`.
3. **Range scans** — `scan_set_tidrange`,
   `scan_getnextslot_tidrange`.
4. **TID fetching** — `tuple_fetch_row_version`,
   `tuple_tid_valid`, `tuple_get_latest_tid`.
5. **DML** — `tuple_insert`, `tuple_update`, `tuple_delete`,
   `tuple_lock`, `multi_insert`, `tuple_insert_speculative`,
   `tuple_complete_speculative`.
6. **Build** — `relation_set_new_filelocator`,
   `relation_nontransactional_truncate`, `relation_copy_data`,
   `relation_copy_for_cluster`, `relation_vacuum`,
   `scan_analyze_next_block`, `scan_analyze_next_tuple`.
7. **Sample-scan** — `scan_sample_next_block`,
   `scan_sample_next_tuple`.
8. **Bitmap-scan** — `scan_bitmap_next_block`,
   `scan_bitmap_next_tuple`.
9. **Index-build support** — `index_build_range_scan`,
   `index_validate_scan`.
10. **Estimation** — `relation_estimate_size`,
    `relation_size`, `relation_needs_toast_table`,
    `relation_toast_am`.
11. **Parallel** — `parallelscan_estimate`,
    `parallelscan_initialize`, `parallelscan_reinitialize`.

## The slot_callbacks — types vary by AM

```c
const TupleTableSlotOps *(*slot_callbacks) (Relation rel);
```

[verified-by-code `tableam.h:336`]

The heap AM returns `TTSOpsBufferHeapTuple`. A columnar AM
might return a custom slot ops that materializes per
attribute on demand.

The executor calls this when allocating slots for a scan;
the AM gets to decide the in-memory representation of its
tuples.

## scan_begin and scan_getnextslot — the iteration

[verified-by-code `tableam.h:360, 383`]

```c
TableScanDesc (*scan_begin) (Relation rel, Snapshot snap,
                             int nkeys, ScanKey key,
                             ParallelTableScanDesc pscan,
                             uint32 flags);

bool (*scan_getnextslot) (TableScanDesc scan,
                          ScanDirection direction,
                          TupleTableSlot *slot);
```

`scan_begin` sets up state; `scan_getnextslot` returns the
next tuple as a populated slot. Returns false at end-of-scan.

The flags (`SO_TYPE_SEQSCAN`, `SO_ALLOW_STRAT`, etc.)
inform the AM about caller intentions — sequential
order? Allowed to use BufferAccessStrategy? Sync-scan
candidate?

## tuple_insert — adding rows

[verified-by-code `tableam.h:546-548`]

```c
void (*tuple_insert) (Relation rel, TupleTableSlot *slot,
                      CommandId cid, int options,
                      BulkInsertState bistate);
```

Inserts the slot's content as a row. `options` flags include
`TABLE_INSERT_SKIP_FSM`, `TABLE_INSERT_FROZEN`,
`TABLE_INSERT_NO_LOGICAL`. `bistate` is a hint for
bulk-insert optimizations.

The AM's responsibility: WAL-log the insert, update the FSM
if relevant, return the TID via the slot's `tts_tid` field.

## tuple_update — modify-in-place vs not

[verified-by-code `tableam.h:563-587`]

```c
TM_Result (*tuple_update) (Relation rel,
                           ItemPointer otid,
                           TupleTableSlot *slot,
                           CommandId cid, Snapshot snapshot,
                           Snapshot crosscheck, bool wait,
                           TM_FailureData *tmfd,
                           LockTupleMode *lockmode,
                           TU_UpdateIndexes *update_indexes);
```

Returns a `TM_Result` enum: success, self-modified,
updated-by-other, deleted-by-other, etc.

The heap AM does MVCC-style insert-new + mark-old-as-
updated. A columnar AM might shadow-page or rewrite the
column block.

## tuple_delete — by TID

```c
TM_Result (*tuple_delete) (...);
```

Marks the tuple at TID as deleted. Same `TM_Result`
return.

The heap AM sets `t_xmax` + `HEAP_XMAX_*` flags. The row
stays in place; VACUUM eventually removes.

## The build callbacks — CREATE/REINDEX support

`relation_set_new_filelocator` is called when CREATE TABLE
or rewrite assigns a fresh `RelFileNumber`. The AM creates
the initial empty storage.

`scan_analyze_next_block` / `_next_tuple` are called by
ANALYZE to sample the relation for statistics.

`index_build_range_scan` is called during CREATE INDEX —
the AM iterates its tuples for the index AM to consume.

## TOAST integration

```c
bool (*relation_needs_toast_table) (Relation rel);
Oid  (*relation_toast_am) (Relation rel);
```

The AM declares whether its relations need a separate
TOAST relation + which AM the TOAST relation uses. Heap
uses heap for TOAST too. Custom AMs might tie to a
different TOAST strategy.

## Parallel-scan support

```c
Size (*parallelscan_estimate) (Relation rel);
Size (*parallelscan_initialize) (Relation rel, ParallelTableScanDesc pscan);
void (*parallelscan_reinitialize) (Relation rel, ParallelTableScanDesc pscan);
```

Three callbacks for parallel-aware AMs. The estimate function
returns DSM size; initialize populates it; reinitialize
resets between Gather batches.

## Common review-time concerns

- **Adding a new table AM** is substantial — every function
  pointer must be filled or stubbed.
- **The slot type must match the AM's expected layout** —
  heap uses BufferHeapTuple; custom AMs need custom ops.
- **WAL emission is the AM's responsibility** — modifying
  the page without WAL = no replication, no crash recovery.
- **TM_Result values must be honored** — partial failures
  (`TM_Updated`, `TM_BeingModified`) drive caller retry
  logic.
- **Existing IndexAm code calls back via the TableAm's
  `index_build_range_scan`** — your AM must support it.

## Invariants

- **[INV-1]** Every function pointer must be non-NULL or
  carefully optional.
- **[INV-2]** The AM declares its slot type via
  `slot_callbacks`.
- **[INV-3]** DML callbacks return TM_Result; caller acts
  on the value.
- **[INV-4]** WAL emission is the AM's job; modifying state
  without WAL breaks recovery.
- **[INV-5]** Parallel-scan callbacks required iff the AM
  supports parallel scanning.

## Useful greps

- The full struct:
  `grep -A100 'typedef struct TableAmRoutine' source/src/include/access/tableam.h | head -110`
- The heap impl:
  `grep -RIn 'heapam_methods\|heap_tableam_handler' source/src/backend/access/heap | head -10`
- TM_Result values:
  `grep -n 'TM_Result\|TM_Ok\|TM_Updated\|TM_Deleted' source/src/include/access/tableam.h | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heapam_handler.c`](../files/src/backend/access/heap/heapam_handler.c.md) | — | heap AM handler |
| [`src/include/access/tableam.h`](../files/src/include/access/tableam.md) | 321 | TableAmRoutine struct |
| [`src/include/access/tableam.h`](../files/src/include/access/tableam.md) | — | full type |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-table-am`](../scenarios/add-new-table-am.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/data-structures/indexamroutine.md` — companion
  index-AM vtable.
- `knowledge/subsystems/access-heap.md` — the heap impl.
- `knowledge/idioms/heaptuple-update-chain.md` — chain
  semantics specific to heap.
- `knowledge/data-structures/tupletableslot.md` — slots
  carry the AM's tuple representation.
- `.claude/skills/access-method-apis/SKILL.md` — AM skill.
- `source/src/include/access/tableam.h` — full type.
- `source/src/backend/access/heap/heapam_handler.c` —
  heap AM handler.
