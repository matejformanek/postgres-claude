---
path: src/test/modules/test_bitmapset/test_bitmapset.c
anchor_sha: e18b0cb7344
loc: 768
depth: read
---

# src/test/modules/test_bitmapset/test_bitmapset.c

## Purpose

Coverage harness for the `Bitmapset` API in `nodes/bitmapset.h` — the
variable-length bitmap used pervasively in the planner (RelOptInfo
`relids`, join `required_relids`, equivalence-class `ec_relids`, …). Wraps
every public `bms_*` function as a SQL-callable that takes Bitmapsets as
text-encoded nodes (via `nodeToString`/`stringToNode`) so regression queries
can build, manipulate, and inspect sets directly. Also includes a
`test_random_operations` driver for fuzz coverage. `[verified-by-code]`

## Public symbols

About 30 SQL-callable wrappers covering the full Bitmapset surface, all
declared `PG_FUNCTION_INFO_V1` at `test_bitmapset.c:34-65`:

`test_bms_make_singleton`, `test_bms_add_member`, `test_bms_del_member`,
`test_bms_is_member`, `test_bms_num_members`, `test_bms_copy`,
`test_bms_equal`, `test_bms_compare`, `test_bms_is_subset`,
`test_bms_subset_compare`, `test_bms_union`, `test_bms_intersect`,
`test_bms_difference`, `test_bms_is_empty`, `test_bms_membership`,
`test_bms_singleton_member`, `test_bms_get_singleton_member`,
`test_bms_next_member`, `test_bms_prev_member`, `test_bms_hash_value`,
`test_bms_overlap`, `test_bms_overlap_list`, `test_bms_nonempty_difference`,
`test_bms_member_index`, `test_bms_add_range`, `test_bms_add_members`,
`test_bms_int_members`, `test_bms_del_members`, `test_bms_replace_members`,
`test_bms_join`, `test_bitmap_hash`, `test_bitmap_match`,
plus `test_random_operations`.

## Internal landmarks

- `BITMAPSET_TO_TEXT(bms)` / `TEXT_TO_BITMAPSET(str)` macros (`:88-89`)
  serialize via `nodeToString`/`stringToNode`. This is the only
  user-accessible representation of a Bitmapset — there's no scalar
  `bitmapset` SQL type.
- `PG_ARG_GETBITMAPSET(n)` (`:95`) treats SQL NULL as the empty set, which
  matches the C-level convention that `NULL` Bitmapset pointer == empty.
- `EXPECT_TRUE` / `EXPECT_NOT_NULL` macros (`:71-85`) elog(ERROR) with
  file:line on mismatch — the boilerplate pattern shared with `test_lfind`,
  `test_radixtree`, etc.
- `test_random_operations` is the fuzz driver: random sequence of add/del/
  union/intersect/difference operations on a pair of sets with a parallel
  reference implementation, checking equivalence at each step.

## Invariants & gotchas

- **Test module — never load in production.**
- Most Bitmapset functions are **mutating** (e.g. `bms_add_member` modifies
  in place and may return a different pointer if reallocated) — the test
  wrappers re-emit the returned pointer as text, so SQL callers see the
  post-mutation state.
- `bms_singleton_member` errors out on non-singleton; `bms_get_singleton_member`
  returns -1. The test exercises both.
- The "Bitmapset is just a `Node` for serialization" property is what
  makes the text-encoding wrappers work — see `_outBitmapset` /
  `_readBitmapset` in `outfuncs.c`/`readfuncs.c`.

## Cross-refs

- `source/src/backend/nodes/bitmapset.c` — implementation under test.
- `source/src/include/nodes/bitmapset.h` — API.
- `source/src/backend/nodes/outfuncs.c`, `readfuncs.c` — the
  `nodeToString`/`stringToNode` plumbing this test rides on.
