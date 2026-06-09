# `src/include/lib/binaryheap.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 69

## Role

Simple array-backed binary heap (max-heap or min-heap depending on
comparator sign). Holds `Datum` (backend) or `void *` (frontend) per
slot. Consumers include `nbtree` parallel page split metadata,
`tuplesort` merge passes, and any executor node needing top-N.
[verified-by-code] `source/src/include/lib/binaryheap.h:11-50`

## Public API

- `binaryheap_allocate(capacity, compare, arg)` —
  `source/src/include/lib/binaryheap.h:52`
- `binaryheap_add_unordered` + `binaryheap_build` — bulk-load O(n)
- `binaryheap_add` — incremental O(log n)
- `binaryheap_first` / `binaryheap_remove_first` /
  `binaryheap_remove_node` / `binaryheap_replace_first`
- Empty/size/get-node macros at lines 65-67.

## Invariants

- INV-1: `bh_has_heap_property` is debug-only cross-check that
  `add_unordered` requires a subsequent `binaryheap_build` before
  any ordered op. [verified-by-code]
  `source/src/include/lib/binaryheap.h:37`
- INV-2: `bh_nodes[FLEXIBLE_ARRAY_MEMBER]` — fixed `bh_space`
  capacity; no auto-grow. Caller sizes upfront.

## Notable internals

- Datum/void* split is purely a frontend/backend distinction
  (line 20-24) — frontend can't see `Datum`.

## Trust boundary (Phase D)

None. Generic primitive, fixed capacity, no user input path.

## Cross-refs

- `knowledge/files/src/include/lib/pairingheap.h.md` — alternative
  priority queue used by GiST KNN and walsender lag tracking
- `knowledge/files/src/include/lib/sort_template.h.md`

## Issues

None.
