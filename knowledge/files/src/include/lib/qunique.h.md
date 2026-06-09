# `src/include/lib/qunique.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 67

## Role

Unique-in-place on a pre-sorted array (analogue of C++
`std::unique`). Two flavours: `qunique` (qsort-style comparator)
and `qunique_arg` (qsort_arg-style comparator with arg). Both
`static inline`. [verified-by-code]
`source/src/include/lib/qunique.h:20-65`

## Public API

- `qunique(array, n, width, compare)` → new size
- `qunique_arg(array, n, width, compare, arg)` → new size

## Invariants

- INV-1: caller MUST have pre-sorted the array with a comparator
  consistent with the one passed to qunique; behaviour is silently
  wrong otherwise. [from-comment] lines 17-18.
- INV-2: shifts via raw `memcpy(width)` — overlapping ranges are
  fine because dest j ≤ source i always.

## Trust boundary (Phase D)

None.

## Cross-refs

- `knowledge/files/src/include/lib/sort_template.h.md`

## Issues

None.
