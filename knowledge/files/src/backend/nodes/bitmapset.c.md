# bitmapset.c

- **Source:** `source/src/backend/nodes/bitmapset.c` (~1100 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## Purpose

Generic set of nonnegative integers, with the convention that the
maximum value is small (a few hundred at most). The implementation is
a sequence of `bitmapword`s (64-bit if `SIZEOF_VOID_P >= 8`, else
32-bit). Used pervasively by the planner: relids in `RelOptInfo`,
attribute sets in `RangeTblEntry.selectedCols`, parameter ids, etc.
`:1-30 bitmapset.c`, `:1-16 bitmapset.h` `[from-comment]`

## Representation invariants

- **Empty set ≡ NULL.** `bms_is_empty(a) == ((a) == NULL)`.
  `bitmapset.h:118` `[verified-by-code]`
- **Trailing zero words are forbidden** — every non-NULL Bitmapset has
  `words[nwords-1] != 0`. Operations that could leave a trailing-zero
  tail must trim it (or call `bms_copy_and_free` under
  REALLOCATE_BITMAPSETS). `:9-12` `[from-comment]`,
  `bms_is_valid_set:78-94` `[verified-by-code]`
- **Inputs may be recycled.** Functions like `bms_add_member`,
  `bms_del_member`, `bms_int_members`, `bms_join` may modify and
  return their input *or* free it and return a fresh one. Callers
  must use the returned pointer; the old pointer may be dangling.
  `:19-22`, `bitmapset.h:120-129` `[from-comment]`
- `Bitmapset` is a NodeTag-bearing struct (`T_Bitmapset`) with custom
  copy/equal and special read/write — `bitmapset.h:49-56`,
  `pg_node_attr(custom_copy_equal, special_read_write, no_query_jumble)`.
  `[verified-by-code]`

## Word layout

```
WORDNUM(x) = x / BITS_PER_BITMAPWORD
BITNUM(x)  = x % BITS_PER_BITMAPWORD
```

A non-NULL set has `>= 1` word, so the implementation uses
`do { ... } while` over the words array — saving one branch per call
for the common single-word case. `:9-17` `[from-comment]`

## REALLOCATE_BITMAPSETS `:24-30, :97-116`

Debug-only build flag. Every mutation copies the set to a fresh
allocation and `pfree`s the original, so any stale pointer becomes a
use-after-free Valgrind hit. Mirrors the DEBUG_LIST_MEMORY_USAGE
pattern in `list.c`.

## API surface (from `bitmapset.h:94-138`)

Constructors / observers:
- `bms_make_singleton(x)`, `bms_copy`, `bms_free`
- `bms_is_member`, `bms_member_index`, `bms_num_members`
- `bms_membership(a)` → `BMS_EMPTY_SET` / `BMS_SINGLETON` / `BMS_MULTIPLE`
  (cheaper than `bms_num_members` when you only need a coarse answer)
- `bms_is_empty(a)` is a macro: `(a) == NULL`

Set ops returning fresh sets (don't recycle):
- `bms_union`, `bms_intersect`, `bms_difference`
- `bms_equal`, `bms_compare`, `bms_subset_compare`
  (`BMS_EQUAL` / `BMS_SUBSET1` / `BMS_SUBSET2` / `BMS_DIFFERENT`)
- `bms_is_subset`, `bms_overlap`, `bms_overlap_list`,
  `bms_nonempty_difference`
- `bms_singleton_member` (errors if not a singleton),
  `bms_get_singleton_member` (out-param, false if not singleton)

Set ops that **recycle** their left input (must reassign):
- `bms_add_member`, `bms_del_member`
- `bms_add_members`, `bms_replace_members`, `bms_int_members`,
  `bms_del_members`, `bms_add_range`
- `bms_join(a, b)` — like `bms_add_members(a, b)` but `b` is also
  freed (or its storage reused)

Iteration `bitmapset.h:131-133`:
- `bms_next_member(a, prevbit)` / `bms_prev_member(a, prevbit)` —
  pass `-1` to start. The canonical loop is:
  ```c
  int  x = -1;
  while ((x = bms_next_member(set, x)) >= 0) { ... }
  ```

Hash-table support `bitmapset.h:135-138`:
- `bms_hash_value(a)`
- `bitmap_hash(key, keysize)` / `bitmap_match(k1, k2, keysize)` for
  use as `HASHCTL` callbacks where the key is a `Bitmapset *`.

## Cute bit tricks

- `RIGHTMOST_ONE(x) = (signedbitmapword)x & -(signedbitmapword)x` —
  classic isolate-lowest-set-bit trick, depends on two's complement
  arithmetic. `:53-70` `[from-comment]`
- `HAS_MULTIPLE_ONES(x) = (RIGHTMOST_ONE(x) != x)` — fast singleton
  test per word. `:72` `[verified-by-code]`
- `bmw_leftmost_one_pos` / `bmw_rightmost_one_pos` / `bmw_popcount`
  dispatch on word size to `pg_bitutils` (uses native CPU
  instructions where available). `bitmapset.h:77-87`
  `[verified-by-code]`

## Why planner code is full of bitmapsets

A typical query has at most a few hundred range-table entries and a
few thousand attributes per table. Bitmapsets give O(1) membership,
O(N/64) union/intersect, fit in one or two cache lines for typical
sizes, and serialize compactly into the plan-tree text form. They
totally dominate `pathnodes.h` (relids, required_outer, eclass_indexes,
parents, …).

## Cross-references

- Header: `source/src/include/nodes/bitmapset.h`
- Used by: `pathnodes.h`, `parsenodes.h` (`selectedCols`,
  `updatedCols`), `optimizer/path/*`, basically all of planner.
- `tidbitmap.c` borrows `bitmapword` / `BITS_PER_BITMAPWORD` from this
  header for its per-page bitmaps. `tidbitmap.c:68` `[verified-by-code]`
