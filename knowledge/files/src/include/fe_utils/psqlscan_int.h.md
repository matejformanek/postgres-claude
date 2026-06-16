---
path: src/include/fe_utils/psqlscan_int.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 155
depth: read
---

# `src/include/fe_utils/psqlscan_int.h`

- **File:** `source/src/include/fe_utils/psqlscan_int.h` (155 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Internal declarations for the psql/pgbench shared SQL lexer. Declares `PsqlScanStateData` —
the full working state of the flex scanner — and the functions exported by `psqlscan.l` for
use only by *compatible add-on lexers* (e.g. `psqlscanslash.l`). This header is meant to be
included from the body of a flex `.l` file where `YY_BUFFER_STATE`/`yyscan_t` are already
defined; the typedefs at the top are stubs so the header can be compiled standalone for header
validity checks. The public-facing API is in [[knowledge/files/src/include/fe_utils/psqlscan.h]].
`[from-comment]` (:1-42)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `YY_BUFFER_STATE` / `yyscan_t` (stubs) | :54-55 | Standalone-compile placeholders for flex types. |
| `StackElem` | :63 | One frame of the psql-variable-expansion buffer stack. |
| `PsqlScanStateData` | :78 | The entire re-entrant lexer state (see below). |
| `psqlscan_push_new_buffer` / `_pop_buffer_stack` | :137-139 | Push/pop a variable-expansion buffer. |
| `psqlscan_select_top_buffer` | :140 | Re-point flex at the top stacked buffer. |
| `psqlscan_var_is_current_source` | :141 | Recursion guard: is `varname` already being expanded? |
| `psqlscan_prepare_buffer` | :143 | Wrap a string in a flex buffer (FF-substitution for unsafe encodings). |
| `psqlscan_emit` | :146 | Emit scanned text, undoing FF-substitution. |
| `psqlscan_extract_substring` | :147 | Pull a substring back out (FF-aware). |
| `psqlscan_escape_variable` / `_test_variable` | :149-152 | Variable-substitution callbacks. |

## Internal landmarks

- **The 0xFF-substitution trick** (`:9-21`): in "unsafe" client encodings (where non-first
  bytes of a multibyte character can be < 0x80), the lexer substitutes `0xFF` for every
  non-first byte before handing text to flex, so the lexing rules (which treat all high-bit
  bytes alike) cannot be fooled into matching a continuation byte as ASCII. `psqlscan_emit()`
  looks back at the original string to restore the real bytes. `[from-comment]` (:9-21)
- **Multiple physical flex lexers, one state** (`:23-34`): psql scans different parts of the
  same input with separately-compiled lexers (`psqlscan.l` + `psqlscanslash.l`); this works
  only because they are re-entrant (all state in the `yyscan_t`) and share the
  `PsqlScanStateData`. The comment warns it is "unlikely to work nicely" if the lexers use
  different flex versions/options. `[from-comment]` (:23-34)
- `buffer_stack` (`:84`) of `StackElem` implements psql variable expansion: each `:var`
  reference pushes the variable's text as a new flex buffer; popping resumes the outer buffer
  (`scanbufhandle`). `[verified-by-code]`
- BEGIN…END block tracking (`:116-122`): `identifier_count`, `identifiers[4]`, `begin_depth`
  let the lexer avoid ending a query at a semicolon inside a function-body `BEGIN … END`. `[from-comment]` (:116-119)

## Invariants & gotchas

- The standalone-compile typedefs (`:54-55`) must **not** be in scope when the file is included
  from a real `.l` body — there the flex-generated definitions win. The `#ifndef` guard plus
  flex's own include ordering keep them from colliding. `[from-comment]` (:49-53)
- `start_state` is "adopted by yylex() on entry and updated on exit" (`:105-110`) — the lexer's
  start condition persists across input lines until `psql_scan_reset`. Forgetting to reset
  leaves quote/comment nesting state dangling between statements. `[from-comment]` (:105-110)

## Invariants & gotchas — BEGIN/END heuristic

- `identifiers[4]` (`:121`) records only the **first few** identifiers of a statement to guess
  whether a `BEGIN` opens a transaction vs a PL block. A fixed 4-slot buffer is a heuristic,
  not a parser — it can misclassify unusual statement shapes. This is the same class of
  "documented-fragile lexer heuristic" the A9 plpgsql sweep flagged (the `pl_gram.y` INTO /
  integer-FOR / PERFORM heuristics). `[verified-by-code]`

## Cross-refs

- Public API: [[knowledge/files/src/include/fe_utils/psqlscan.h]].
- Implementations: `src/fe_utils/psqlscan.l`, `src/bin/psql/psqlscanslash.l` (the A4 sweep
  noted `psqlscan.l` as an uncovered corpus gap).

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: BEGIN/END detection uses a fixed 4-identifier window]**
  `psqlscan_int.h:121` — `identifiers[4]` records only the first few identifiers to decide
  whether a `BEGIN` is transactional or a PL block boundary; a heuristic that can misfire on
  unusual statement prefixes. Benign (worst case is a mis-split at a semicolon, surfaced as a
  syntax error to the user), but a known-fragile lexer heuristic in the same family as the A9
  plpgsql grammar heuristics. Severity `nit`. Mirrored to `knowledge/issues/fe_utils.md`.
