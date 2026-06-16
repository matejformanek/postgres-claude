# `src/backend/utils/adt/tsginidx.c`

## Purpose

GIN opclass support for `tsvector_ops`. `gin_extract_tsvector`
emits one entry per lexeme; `gin_extract_tsquery` emits the search
keys; `gin_tsquery_consistent` (and `_triconsistent`) walks the
tsquery against the bool array of "key present?" answers from GIN.
359 lines.

## Key functions

- `gin_cmp_tslexeme` — `tsginidx.c:24`. Lexeme comparator (`tsCompareString`).
- `gin_cmp_prefix` — `:40`. Comparator with prefix-match semantics.
  Forces `+1` on `<0` to halt scan.
- `gin_extract_tsvector` — `:64`. One Datum per lexeme; sets
  `*nentries = vector->size`.
- `gin_extract_tsquery` — Recursively traverses tsquery; emits an
  entry per QI_VAL operand, marking each as prefix or not via
  `extra_data` (the `searchMode` flag for GIN scan).
- `gin_tsquery_consistent` / `_triconsistent` — Calls `TS_execute`
  with a per-key callback that reads GIN's `check[]` array. Three-
  valued logic to handle MAYBE for prefix and OR branches.

## Phase D notes

GIN consistent functions are the **correctness lynchpin**: returning
`true` when the indexed row might not actually match causes false
positives (then verified by recheck), but returning `false` when it
might match causes data loss (missing rows from the result). The
tri-state consistent func is the safer pattern.

The `extra_data` channel is used to pass per-key flags (prefix
match) from `extract_tsquery` through GIN's storage into the
consistent function. Format coupling: extract and consistent must
agree on the layout.

## Potential issues

- [ISSUE-correctness: `gin_cmp_prefix` returns `1` on `<0` to halt
  scan (`:55-56`). The convention is non-obvious — a caller
  refactoring this to "natural" comparison would silently break
  prefix scans by causing them to miss matches. (low)]
- [ISSUE-undocumented-invariant: `extra_data` layout coupling
  between `gin_extract_tsquery` and `gin_tsquery_consistent` is
  documented only by code — schema drift between the two would be
  a silent correctness bug. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
