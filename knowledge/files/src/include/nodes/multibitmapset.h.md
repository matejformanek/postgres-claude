# src/include/nodes/multibitmapset.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 39 [verified-by-code]

## Role

Two-level integer set: `List<Bitmapset>`. The outer List index is one
identifier dimension, bit positions within the inner Bitmapset are the
second. Typical use: `(varno, varattno)` pairs across a query, where
varno gives the rangetable slot and varattno gives the column.

## Public API

- `mbms_add_member(List *a, int listidx, int bitidx) -> List*` —
  insert single (listidx, bitidx) pair (`:33`).
- `mbms_add_members(List *a, const List *b) -> List*` — set-union of
  two multibitmapsets (`:34`).
- `mbms_int_members(List *a, const List *b) -> List*` — set-intersect
  (`:35`).
- `mbms_is_member(int listidx, int bitidx, const List *a) -> bool`
  (`:36`).
- `mbms_overlap_sets(const List *a, const List *b) -> Bitmapset*` —
  the listidxs where a and b share at least one bit (`:37`).

## Invariants

- INV-MBMS-NIL: empty set = `NIL` (header comment `:13-14`
  [from-comment]); NOT a List of empty bitmapsets. But an
  intermediate state where an inner bitmapset has been emptied is
  also valid — readers must skip NULL bitmapsets.
- INV-MBMS-LENGTH: outer List length is just-large-enough to hold
  the highest listidx; can grow via `mbms_add_member` lengthening
  with `NULL` filler bitmapsets.

## Notable internals

- Operations parallel the bitmapset API — only the small fraction
  currently used by the planner / parser is built out (`:16-19`
  [from-comment]). Future contributions should follow same
  signatures.

## Trust boundary / Phase D surface

- Pure data-structure header; no privilege boundary.
- Used by query-jumble (`queryjumble.c`?) and by the planner for
  tracking referenced (RTE, attr) pairs across joins — buggy ops
  could allow planner to consider an invalid expression
  push-down, but that's correctness, not privilege.

## Cross-references

- `nodes/bitmapset.h` — inner element type.
- `nodes/pg_list.h` — outer container.
- Consumers: planner pull-up/push-down passes, ENR tracking.

## Issues / drift

- `[ISSUE-DOC: "small fraction of [the API] has been built out" — adding members ad-hoc without consistent naming is a future-confusion risk (low)] — source/src/include/nodes/multibitmapset.h:16-19`
