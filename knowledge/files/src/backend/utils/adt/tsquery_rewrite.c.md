# `src/backend/utils/adt/tsquery_rewrite.c`

## Purpose

`ts_rewrite(query, target, substitute)` SQL function. Walks the
QTNode tree of `query`, finds subtrees matching `target`, and
replaces them with `substitute`. Two variants: direct
target/substitute arguments, and a SELECT-from-table form that uses
SPI to fetch (target, substitute) pairs. 462 lines.

## Key functions

- `findeq` — `tsquery_rewrite.c:120`. Test single-node match (after
  QTNSort canonicalisation).
- `dofindsubquery` — `:206`. Recursive walker; `check_stack_depth` at
  `:209`, `CHECK_FOR_INTERRUPTS` at `:212`. Drops NULL-replaced
  children and collapses single-child operators.
- `findsubquery` — `:267`. Public wrapper, threads `isfind` flag.
- `tsquery_rewrite_query` — `:280`. SQL entry; pre-canonicalises both
  trees with QTNTernary + QTNSort, then `findsubquery`.
- `tsquery_rewrite` — table-driven form using SPI. Sets up an SPI
  cursor, iterates rows, calls `findsubquery` per (target,
  substitute) pair until none match.

## Phase D notes

This is the **user-controlled tree-rewrite path** — substitute can
itself contain operands that match other targets in the same SPI
loop, so the SPI-driven form iterates until quiescence. **No cycle
detection.** A self-referential SPI rewrite table where target ≡
substitute (after canonicalisation) is filtered out by the
"already-rewritten" marker `QTN_NOCHANGE` (`:218`) but the
interaction is subtle.

The substitute tree is **deep-copied per match** to preserve
ownership (`QTNCopy` in tsquery_util.c). For a query with N
matches and substitute size S, memory grows N*S.

Recursion uses `check_stack_depth` plus `CHECK_FOR_INTERRUPTS`,
both at every recursive level — query cancellation works through
deep rewrites.

## Potential issues

- [ISSUE-dos: SPI-driven `ts_rewrite(query, sql_select)` runs the
  SELECT, then for each row attempts a rewrite. A pathological
  user-owned aliases table with many rows and a query containing
  matching subtrees causes O(rows × tree_size) work per call. No
  per-call timeout. (low, maybe — user-owned table)]
- [ISSUE-undocumented-invariant: The `QTN_NOCHANGE` flag prevents
  re-rewriting at the same node within one pass — but across SPI
  iterations the flag is cleared (`QTNClearFlags`), so a sequence
  `(a -> b), (b -> a)` could cycle. Read the SPI loop closely:
  `findsubquery`'s `*isfind` is the loop guard, so once nothing
  changes the loop exits. **Safe.** `[verified-by-code]` (n/a)]
- [ISSUE-stale-todo: None visible.]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
