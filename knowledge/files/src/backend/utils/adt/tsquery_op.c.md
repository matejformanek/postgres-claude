# `src/backend/utils/adt/tsquery_op.c`

## Purpose

Binary operators between two `tsquery` values: `tsquery_and`,
`tsquery_or`, `tsquery_not`, `tsquery_phrase` (and distance variant).
Plus `tsquery_numnode` (count nodes) and equality/comparison opers.
Used to build composite queries programmatically. 359 lines.

## Key functions

- `tsquery_numnode` — `tsquery_op.c:23`. Return `query->size`.
- `join_tsqueries` — `:33`. Static helper; builds a QTNode with two
  children (deep-copied via `QT2QTN`).
- `tsquery_and`, `tsquery_or` — `:54`, `:90`. Build a new operator
  node with both inputs.
- `tsquery_phrase`, `tsquery_phrase_distance` — Phrase combinator
  with default distance 1 or user-supplied `int32` distance. Range-
  checked against `MAXENTRYPOS`.
- `tsquery_not` — Prepend NOT.
- `tsq_mcontains`, `tsq_mcontained` — "more contains" operators for
  subquery containment tests (semilattice on lexeme sets).

## Phase D notes

These are pure tree builders — no parser surface. Distance argument
to `tsquery_phrase` is the only user-controlled int; bounded by
`MAXENTRYPOS`.

`tsq_mcontains` decomposes both trees to lexeme-set view, sorts and
checks for set inclusion. O(N log N) in number of operands;
operates on the polish-notation arrays directly without building
QTNode trees, so cheaper than rewrite.

## Potential issues

- [ISSUE-undocumented-invariant: `join_tsqueries` swaps argument
  order (`b` becomes child[0], `a` becomes child[1] at `:46-47`).
  Comment-less reverse ordering is a footgun for new authors. (low)]
- [ISSUE-dead-code: None visible.]
