# src/include/common/unicode_case.h

## Purpose

Public API for Unicode case conversion (lower / title / upper /
casefold) at both the per-codepoint level and the per-UTF-8-string
level. Title casing takes a callback that returns word boundaries.

## Role in PG

Shared **frontend + backend**. Backend uses these for the builtin
provider's `lower()/upper()/initcap()` family when the collation is
the "C.UTF-8"/builtin Unicode locale. Frontend uses them
transitively via saslprep / SCRAM. Backed by the generated
`unicode_case_table.h` (not in scope here).

## Key declarations

- `typedef size_t (*WordBoundaryNext)(void *wbstate)` — caller-supplied
  boundary iterator for titlecasing. (`unicode_case.h:17`)
- Per-codepoint, "simple" 1->1 mappings:
  `unicode_lowercase_simple`, `unicode_titlecase_simple`,
  `unicode_uppercase_simple`, `unicode_casefold_simple`.
  (`unicode_case.h:19-22`)
- Per-UTF-8-string variants:
  `unicode_strlower`, `unicode_strtitle`, `unicode_strupper`,
  `unicode_strfold`. All return required output length (caller may
  pass `dstsize=0` to size first). The `full` flag toggles
  multi-codepoint mappings (e.g. German sharp s → SS).
  (`unicode_case.h:23-31`)

## Phase D notes

Input must be valid UTF-8 — invalid input is an Assert. The
`pg_unicode_to_server` path uses these; any mismatch between a
frontend's case conversion and the backend's would manifest as an
identifier folding bug. saslprep normalisation lives in
`unicode_norm.c`, not here.

## Potential issues

None at the header level.
