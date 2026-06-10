# src/include/parser/parsetree.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 61 [verified-by-code]

## Role

Tiny accessor library for parse-tree components: range-table fetch,
attribute-name lookup, target-list lookup, FOR UPDATE/SHARE clause
extraction. Lives between the parser output and the planner's
consumption.

## Public API

- `rt_fetch(rangetable_index, rangetable)` macro — 1-indexed
  `list_nth` casting to `RangeTblEntry *`; crashes on out-of-range
  (`:31-32` [from-comment]).
- `get_rte_attribute_name(RangeTblEntry *, AttrNumber) -> char *`
  (`:38`).
- `get_rte_attribute_is_dropped(RangeTblEntry *, AttrNumber) ->
  bool` (`:43-44`).
- `get_tle_by_resno(List *tlist, AttrNumber resno) -> TargetEntry *`
  (`:52`).
- `get_parse_rowmark(Query *qry, Index rtindex) -> RowMarkClause *`
  (`:59`).

## Invariants

- INV-RT-INDEX-1-BASED: range-table indices in PG are **1-based**
  for historical reasons (`rt_fetch` does `index - 1` internally).
  AttrNumber is also 1-based for real columns (0 means whole-row).
  Mixing this with `list_nth` (0-based) is the single most common
  off-by-one bug source.
- INV-RT-FETCH-NO-BOUNDS-CHECK: macro `:29-32` [from-comment]
  explicitly: "will crash and burn if handed an out-of-range RT
  index". Caller must validate.
- INV-DROPPED-ATTR-ANSWER: `get_rte_attribute_is_dropped` returns
  TRUE for columns that have been ALTER TABLE DROP'd but whose
  attnum still exists in pg_attribute with `attisdropped=true`.
- INV-RESJUNK-AWARE: `get_tle_by_resno` ignores resjunk filtering
  — it returns whatever TargetEntry has matching resno, junk or
  not.

## Notable internals

- The functions are small enough they could be inline; kept as
  externs for historical ABI stability.
- `get_rte_attribute_name` checks `rte->alias->colnames` first,
  then `rte->eref->colnames`, then falls back to relation
  metadata. Returns "?column?" for synthetic columns.

## Trust boundary / Phase D surface

- Pure read-side accessors; no privilege boundary.
- **A14 echo (catalog probing).** `get_rte_attribute_name`
  returns names from `eref` — which were captured at parse
  time. EXPLAIN output uses these. If a renamed column is
  present in a cached plan, the OLD name appears in EXPLAIN —
  potentially exposing a column-rename history.

## Cross-references

- `nodes/parsenodes.h` — `RangeTblEntry`, `TargetEntry`,
  `RowMarkClause`.
- `parser/parse_relation.h` — populates rangetable.
- `optimizer/optimizer.h` — uses these accessors during
  planning.

## Issues / drift

- `[ISSUE-CODE: rt_fetch macro evaluates rangetable_index twice — side-effect-bearing argument (e.g. ++) would be a bug; not documented (low)] — source/src/include/parser/parsetree.h:31-32`
- `[ISSUE-DOC: 1-based rt indexing not mentioned in header — institutional knowledge required (low)] — source/src/include/parser/parsetree.h:31-32`
