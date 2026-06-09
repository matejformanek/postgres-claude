# `src/include/lib/pairingheap.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 105

## Role

Pairing-heap priority queue: O(1) amortized insert + meld, O(log n)
extract-min/max. Used where `binaryheap.h` is unsuitable because
nodes must be embedded (intrusive). Major consumers:

- GiST KNN scan (`gistget.c` — k-nearest-neighbour ordering)
- walsender lag-tracker (`logical/`)
- Some replication-slot wakeup ordering

[verified-by-code] `source/src/include/lib/pairingheap.h:19-35`

## Public API

- `pairingheap_node` — embed in containing struct (first_child /
  next_sibling / prev_or_parent)
- `pairingheap_container(type, member, ptr)` — outer-pointer cast
  via StaticAssertVariableIsOfTypeMacro (lines 43-54)
- `pairingheap_allocate(compare, arg)` / `_initialize` / `_free`
- `pairingheap_add` / `_first` / `_remove_first` / `_remove`
- Macros: `_reset`, `_is_empty`, `_is_singular` (lines 96-103)
- `pairingheap_dump` — only with `PAIRINGHEAP_DEBUG`

## Invariants

- INV-1: comparator semantics identical to `binaryheap`: `<0` iff
  `a<b` for max-heap; reverse for min-heap. [from-comment]
- INV-2: caller embeds `pairingheap_node`; lifetime tracked by
  caller; no allocations inside add/remove.

## Trust boundary (Phase D)

None — generic primitive.

## Cross-refs

- `knowledge/files/src/include/lib/binaryheap.h.md` — array-backed
  peer

## Issues

None.
