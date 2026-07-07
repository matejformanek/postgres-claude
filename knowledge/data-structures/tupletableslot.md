# TupleTableSlot — executor's tuple container

`TupleTableSlot` is the executor-layer wrapper around a tuple.
Plan nodes pass tuples to each other through slots, not raw
`HeapTuple`s, because slots provide an **abstract** interface
that works equally well for tuples that live in shared buffers,
detoasted minimal tuples, virtual computed tuples, and tuples
from foreign data wrappers. The `TupleTableSlotOps` vtable on
each slot decides what backing-storage strategy is in play.

Anchors:
- `source/src/include/executor/tuptable.h:120-144` — the
  base struct [verified-by-code]
- `source/src/include/executor/tuptable.h:147-242` — the
  `TupleTableSlotOps` vtable [verified-by-code]
- `source/src/backend/executor/execTuples.c` — the
  implementations (`TTSOpsVirtual`, etc.)
- `knowledge/subsystems/executor.md` — the executor at large

## The base struct

```c
typedef struct TupleTableSlot
{
    NodeTag      type;
    uint16       tts_flags;
    AttrNumber   tts_nvalid;           /* # of valid values */
    const TupleTableSlotOps *const tts_ops;   /* implementation */
    TupleDesc    tts_tupleDescriptor;
    Datum       *tts_values;           /* per-attribute values */
    bool        *tts_isnull;
    int          tts_first_nonguaranteed;
    MemoryContext tts_mcxt;
    ItemPointerData tts_tid;
    Oid          tts_tableOid;
} TupleTableSlot;
```

[verified-by-code `tuptable.h:120-144`]

- `tts_values[]` / `tts_isnull[]` are the **virtual** view of
  the tuple — one entry per attribute, regardless of backing
  storage. Plan nodes always read through these.
- `tts_nvalid` says how many of those `tts_values[]` entries are
  actually populated; reading attribute N requires
  `tts_nvalid >= N + 1` first via `slot_getsomeattrs(slot, N+1)`.
- `tts_ops` is the vtable; identifies the backing-storage
  strategy.
- `tts_tid` + `tts_tableOid` carry the on-disk identity when
  applicable (heap tuples, foreign-table tuples with an OID
  mapping).

## The four built-in slot ops

[verified-by-code `tuptable.h:248-256`]

| Vtable | Backing | When used |
|---|---|---|
| `TTSOpsVirtual` | `tts_values[]` only | Computed tuples (projection output, ValuesScan) |
| `TTSOpsHeapTuple` | A palloc'd `HeapTuple` | In-memory heap tuples passed between nodes |
| `TTSOpsMinimalTuple` | A `MinimalTuple` (header-less) | Tuplestore / tuplesort spills, hashtable values |
| `TTSOpsBufferHeapTuple` | A `HeapTuple` pinned to a `Buffer` | SeqScan / IndexScan output |

`TTS_IS_VIRTUAL` / `TTS_IS_HEAPTUPLE` / `TTS_IS_MINIMALTUPLE` /
`TTS_IS_BUFFERTUPLE` macros classify a slot.

The distinction matters for **deserialization cost**:

- Virtual is "already decoded"; reading is array indexing.
- Heap / Buffer require `getsomeattrs` to walk the on-disk
  format and populate `tts_values[]`.
- Minimal is similar but with a stripped header.

## The vtable: 11 callbacks

[verified-by-code `tuptable.h:147-242`]

- `init` / `release` — per-slot setup / teardown
- `clear` — drop the contents but keep the descriptor
- `getsomeattrs(slot, natts)` — decode at least `natts`
  attributes into `tts_values` / `tts_isnull`
- `getsysattr(slot, attnum, isnull)` — fetch a system column
  (oid, ctid, xmin, etc.)
- `is_current_xact_tuple` — used for `xmin = MyXid` semantics
- `materialize` — make the slot self-sufficient (decouple from
  buffer pin / external context)
- `copyslot` — copy-into-destination semantics
- `get_heap_tuple` / `get_minimal_tuple` — return the
  slot-owned representation if available
- `copy_heap_tuple(slot)` / `copy_minimal_tuple(slot, extra)` —
  return a freshly-palloc'd independent copy

Custom AMs **rarely** need a custom vtable — the four built-ins
cover almost every shape. Foreign-data wrappers usually use
`TTSOpsVirtual` to project FDW columns.

## The buffer-pin contract

`TTSOpsBufferHeapTuple` slots **hold a buffer pin** as long as
the slot is live. The pin is the slot's guarantee that the
buffer won't be evicted while the slot's `tts_values[]` point
at on-page data.

`ExecMaterialize`, `ExecCopySlot`, and `ExecStoreVirtualTuple`
all explicitly **drop the pin** (by promoting to a virtual or
heap slot, or by `materialize`ing). Plan nodes that hand a
slot off across a memory-context reset must materialize first.

Forgetting to materialize before a context reset = use-after-free.

## The "deformation" pattern

The standard usage:

```c
slot_getsomeattrs(slot, 5);              /* decode first 5 attrs */
Datum first  = slot->tts_values[0];      /* always indexable now */
bool  isnull = slot->tts_isnull[0];
```

`slot_getsomeattrs(slot, N)` is the inline wrapper that calls
`tts_ops->getsomeattrs(slot, N)` only if `tts_nvalid < N`. The
amortization matters — a node that reads attributes 1, 3, 5 in
sequence pays the deformation cost once for "up to attr 5,"
not three times.

## Memory ownership

- The slot itself lives in `tts_mcxt`.
- `tts_values[]` and `tts_isnull[]` arrays are palloc'd in
  `tts_mcxt` at slot creation time.
- The backing tuple (`HeapTuple`, `MinimalTuple`) lives in
  whatever context the slot's vtable chose.
- A "materialized" slot's backing tuple lives in `tts_mcxt`
  too — the slot owns it.

Common bug: pass a slot up across a query-execution-context
reset without materializing. The backing tuple's context gets
reset, but `tts_values[]` (in `tts_mcxt`) still point into the
freed memory.

## Common review-time concerns

- **Always `slot_getsomeattrs(slot, N)` before
  `tts_values[N-1]`**. Reading an undeformed attribute returns
  garbage.
- **Materialize before crossing context boundaries.** Cheap if
  already materialized (no-op); critical if not.
- **Don't manually pin buffers for slots.** The slot vtable
  manages pin lifecycle; manual pins double-count.
- **`tts_tableOid` is not always set.** Some slots leave it as
  `InvalidOid`. Don't rely on it for routing decisions.
- **The vtable pointer is `const`** — once a slot is created,
  its strategy is fixed. To switch strategies, drop and
  recreate the slot.

## Invariants

- **[INV-1]** `tts_values[i]` is only valid when `i < tts_nvalid`.
- **[INV-2]** Buffer-tuple slots hold a buffer pin for the
  duration of the slot's life with that tuple.
- **[INV-3]** Materializing a slot decouples it from external
  resources; the slot then owns its tuple.
- **[INV-4]** The vtable is const; can't change strategy
  mid-life.
- **[INV-5]** `slot_getsomeattrs(slot, N)` ensures
  `tts_nvalid >= N` after the call.

## Useful greps

- All slot consumers in plan nodes:
  `grep -RIn 'ExecStoreHeapTuple\|ExecStoreVirtualTuple\|ExecStoreMinimalTuple\|ExecStoreBufferHeapTuple' source/src/backend/executor | head -30`
- Deformation sites:
  `grep -RIn 'slot_getsomeattrs\|slot_getallattrs' source/src/backend/executor | wc -l`
- The four built-in op tables:
  `grep -n 'const TupleTableSlotOps TTSOps' source/src/backend/executor/execTuples.c`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execTuples.c`](../files/src/backend/executor/execTuples.c.md) | — | implementation of all 4 built-in vtables |
| [`src/include/executor/tuptable.h`](../files/src/include/executor/tuptable.h.md) | 120 | the base struct |
| [`src/include/executor/tuptable.h`](../files/src/include/executor/tuptable.h.md) | 147 | the TupleTableSlotOps vtable |
| [`src/include/executor/tuptable.h`](../files/src/include/executor/tuptable.h.md) | — | struct + vtable + op signatures |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/subsystems/executor.md` — the executor pipeline
  that consumes / produces slots.
- `knowledge/data-structures/heap-tuple-layout.md` — the
  underlying tuple format that `getsomeattrs` parses.
- `.claude/skills/executor-and-planner/SKILL.md` — plan node
  conventions; slot lifetime within `ExecProcNode`.
- `.claude/skills/access-method-apis/SKILL.md` — table AMs
  return slots from `scan_getnextslot`; choosing the right
  vtable.
- `.claude/skills/fmgr-and-spi/SKILL.md` — SRF returns flow
  through slots when using `InitMaterializedSRF`.
- `source/src/backend/executor/execTuples.c` — implementation
  of all 4 built-in vtables.
- `source/src/include/executor/tuptable.h` — struct + vtable
  + op signatures.
