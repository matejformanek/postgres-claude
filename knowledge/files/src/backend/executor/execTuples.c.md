# execTuples.c

- **Source:** `source/src/backend/executor/execTuples.c` (2609 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (slot ops vtables; TupleDesc helpers)

## Purpose

Implements the **TupleTableSlot** abstraction — the executor's universal
container for "a tuple, somehow" — plus TupleDesc construction helpers used
by every node init routine. The slot decouples a tuple's storage format
(heap on disk, heap in palloc, MinimalTuple, virtual values[]/isnull[]) from
its consumers. [from-comment] `:3-46`

## The four slot kinds

Defined as `const TupleTableSlotOps` vtables at `:84-87`:

- `TTSOpsVirtual` — slot is a pure `values[]/isnull[]` array; no materialized
  tuple. Cheapest; used for projection results and computed tuples. `tts_virtual_*`
  functions at `:97+`.
- `TTSOpsHeapTuple` — slot owns a palloc'd `HeapTuple`. `shouldFree` controls
  whether `ExecClearTuple` pfrees the body. Used when the executor needs to
  hand a heap tuple to consumers that expect HeapTupleHeader (triggers, etc).
- `TTSOpsMinimalTuple` — slot owns a `MinimalTuple` (no header, no system
  columns). The compact-on-disk representation used by Sort, HashAgg, Hash,
  tuplestore, and the parallel-worker tuple queue (shm_mq).
- `TTSOpsBufferHeapTuple` — slot references a HeapTuple **inside a shared
  buffer page**, holding a pin. `ExecClearTuple` releases the pin. This is
  the slot you get from heap_getnext during a scan; the pin guarantees the
  tuple pointer stays valid while consumers read it.

The ops vtable is `init/release/clear/getsomeattrs/getsysattr/is_current_xact_tuple/
materialize/copyslot/get_heap_tuple/get_minimal_tuple/copy_heap_tuple/copy_minimal_tuple`.

## Core operations (and their fast paths)

- `ExecStoreHeapTuple`, `ExecStoreBufferHeapTuple`, `ExecStoreMinimalTuple`,
  `ExecStoreVirtualTuple` — type-specific stores; assert that the slot was
  created with the matching ops.
- `ExecClearTuple` — releases whatever resources the slot held (pin / palloc
  body) and sets TTS_FLAG_EMPTY.
- `slot_getsomeattrs(slot, attnum)` — deconstruct columns 1..attnum into
  `tts_values/tts_isnull`. The fast path is the inlined `slot_deform_heap_tuple`
  (`:75-76` decl) which keeps a per-column offset cache (`tts_off`) so repeated
  decoding of the same tuple at the same depth is O(1) extra. `support_cstring`
  variant handles the `cstring` type without nul-terminating.
- `slot_getallattrs` — wrapper that asks for `tupdesc->natts`.
- `ExecMaterializeSlot` — forces a non-virtual slot to own its data (so the
  underlying buffer pin / external pointer can be released).
- `ExecCopySlot(dstslot, srcslot)` — copy a tuple between slots, choosing
  the most efficient path the ops allow.

## TupleDesc helpers

- `ExecTypeFromTL(targetList)` / `ExecCleanTypeFromTL` — build a TupleDesc
  from a TLIST, optionally skipping resjunk entries.
- `ExecTypeFromExprList` — TupleDesc for a list of Exprs (used by SubPlan
  output, ValuesScan, etc.).
- `ExecAssignResultType(planstate, tupdesc)`,
  `ExecInitResultTypeTL(planstate)` / `ExecInitResultTupleSlotTL` —
  called by every Init routine to set up the node's result slot.
- `ExecInitScanTupleSlot(estate, scanstate, tupdesc, ops)` — install the
  raw-scan slot with the chosen ops (BufferHeapTuple for a SeqScan,
  Virtual for a ValuesScan, etc.).
- `BlessTupleDesc(desc)` → entries the desc into the type cache so composite
  outputs get a stable typeid/typmod. Composite SRFs use it.

## Important invariants

- A virtual slot's `tts_values[]` may point into per-tuple-context palloc'd
  memory; the **next ExecClearTuple is what frees it** (if `TTS_FLAG_SHOULDFREE`
  was set). This is the reason every node Reset-s its per-tuple context after
  emitting a row.
- `tts_tid` is only valid on slots that hold a real heap row (Buffer / Heap
  ops). Virtual / Minimal slots invalidate it on clear.
- `tts_tableOid` is set by the scan AM, used by triggers and EvalPlanQual to
  route back to the right partition.

## Tags

- [verified-by-code] vtable declarations + slot_deform_heap_tuple decl.
- [from-comment] header explanation of the per-attribute fast-path.
