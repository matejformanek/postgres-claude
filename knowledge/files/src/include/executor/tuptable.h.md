# tuptable.h

- **Source:** `source/src/include/executor/tuptable.h` (558 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Defines `TupleTableSlot` plus the `TupleTableSlotOps` vtable used for the
four built-in slot kinds (Virtual / HeapTuple / MinimalTuple / BufferHeapTuple)
and any extension-defined slot. The executor's universal tuple container.

## TupleTableSlot

Key fields:
- `tts_flags` — bitmask: TTS_FLAG_EMPTY / TTS_FLAG_SHOULDFREE / TTS_FLAG_SLOW
  (slow path for slot_getsomeattrs) / TTS_FLAG_FIXED.
- `tts_nvalid` — number of attrs valid in tts_values/tts_isnull.
- `tts_ops` — pointer to the slot's TupleTableSlotOps vtable.
- `tts_tupleDescriptor`.
- `tts_values[]`, `tts_isnull[]` — the deformed columns; always present
  even for non-virtual slots, populated lazily by ops->getsomeattrs.
- `tts_mcxt` — memory context the slot was allocated in.
- `tts_tid` — ItemPointer of the underlying row (or invalid).
- `tts_tableOid` — for system-column "tableoid" access on inheritance / partitions.

## TupleTableSlotOps vtable

`init, release, clear, getsomeattrs, getsysattr, is_current_xact_tuple,
materialize, copyslot, get_heap_tuple, get_minimal_tuple, copy_heap_tuple,
copy_minimal_tuple`. Plus `base_slot_size` (alloc size) so generic code can
allocate the right struct subtype.

## Convenience macros

- `TTS_EMPTY(slot)`, `TTS_SHOULDFREE(slot)` — flag tests.
- `TupIsNull(slot)` — null check.
- `ExecClearTuple`, `ExecMaterializeSlot`, `ExecCopySlot`, etc. — declared
  here as inline wrappers around vtable dispatch.

## The four kinds

- `TTSOpsVirtual` — pure values[]/isnull[].
- `TTSOpsHeapTuple` — owns a palloc'd HeapTuple.
- `TTSOpsMinimalTuple` — owns a MinimalTuple.
- `TTSOpsBufferHeapTuple` — borrows a HeapTuple from a pinned shared buffer.

## Tags

- [verified-by-code] struct/ops shapes.
- [from-comment] the "tuple table is a List of independent slots" framing at
  top of file.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/tupletableslot.md](../../../../data-structures/tupletableslot.md)

- [subsystems/executor.md](../../../../subsystems/executor.md)