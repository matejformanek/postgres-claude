# bitmapset.h

- **Source:** `source/src/include/nodes/bitmapset.h` (140 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## Purpose

Declares `Bitmapset` — a set of nonnegative integers — and its API.
Implementation in `bitmapset.c`. See
`knowledge/files/src/backend/nodes/bitmapset.c.md` for full notes on
invariants, cute bit-twiddling, REALLOCATE_BITMAPSETS, etc.

## Type definitions

```c
#if SIZEOF_VOID_P >= 8
#define BITS_PER_BITMAPWORD 64
typedef uint64 bitmapword;
typedef int64  signedbitmapword;
#else
... 32-bit ...
#endif

typedef struct Bitmapset {
    pg_node_attr(custom_copy_equal, special_read_write, no_query_jumble)
    NodeTag    type;
    int        nwords;
    bitmapword words[FLEXIBLE_ARRAY_MEMBER];
} Bitmapset;
```

`:35-56` `[verified-by-code]`

## Comparison enums `:60-74`

- `BMS_Comparison` = `BMS_EQUAL` / `BMS_SUBSET1` / `BMS_SUBSET2` /
  `BMS_DIFFERENT` (result of `bms_subset_compare`).
- `BMS_Membership` = `BMS_EMPTY_SET` / `BMS_SINGLETON` / `BMS_MULTIPLE`
  (result of `bms_membership`).

## Word-op dispatch `:77-87`

Maps `bmw_leftmost_one_pos`, `bmw_rightmost_one_pos`, `bmw_popcount`
to the 32-bit or 64-bit variant in `pg_bitutils`.

## API (full prototype list)

Construction / observation:
- `bms_copy`, `bms_equal`, `bms_compare`, `bms_make_singleton`,
  `bms_free`
- `bms_is_subset`, `bms_subset_compare`, `bms_is_member`,
  `bms_member_index`, `bms_overlap`, `bms_overlap_list`,
  `bms_nonempty_difference`, `bms_singleton_member`,
  `bms_get_singleton_member`, `bms_num_members`, `bms_membership`
- `bms_is_empty(a)` — macro `(a) == NULL`

Set ops that allocate fresh result:
- `bms_union`, `bms_intersect`, `bms_difference`

Set ops that **recycle** the left input (always reassign):
- `bms_add_member`, `bms_del_member`
- `bms_add_members`, `bms_replace_members`, `bms_add_range`
- `bms_int_members`, `bms_del_members`, `bms_join`

Iteration:
- `bms_next_member(a, prevbit)` / `bms_prev_member(a, prevbit)` —
  start at `-1`.

Hash-table support:
- `bms_hash_value(a)`, `bitmap_hash(key, sz)`, `bitmap_match(k1, k2, sz)`

## Cross-references

- Implementation: `source/src/backend/nodes/bitmapset.c`
- Used pervasively in `pathnodes.h` (RelOptInfo.relids,
  required_outer, eclass_indexes, …) and `parsenodes.h`
  (selectedCols, updatedCols, etc.).

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/bitmapset.md](../../../../data-structures/bitmapset.md)
