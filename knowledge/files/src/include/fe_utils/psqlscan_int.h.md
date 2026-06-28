---
path: src/include/fe_utils/psqlscan_int.h
anchor_sha: 419ce13b7019f906ebc010af3be09a9deffc2a47
loc: 158
depth: read
---

# `src/include/fe_utils/psqlscan_int.h`

- **File:** `source/src/include/fe_utils/psqlscan_int.h` (158 lines)
- **Last verified commit:** `419ce13b7019` (re-verified + re-pinned
  2026-06-28 by pg-quality-auditor AUDIT mode after anchor-bump
  `f0a4f280b4d3..419ce13b7019`; doc had been pinned at `4b0bf0788b0`.
  Triggering commit `049b742daad0` ("psql: Tighten heuristics for
  BEGIN/END within CREATE SCHEMA") is a **semantic** change to the
  BEGIN/END block-tracking state, not just line drift — see the
  rewritten "BEGIN/END heuristic" section below. LOC 155→158.)

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
| `psqlscan_push_new_buffer` / `_pop_buffer_stack` | :140-142 | Push/pop a variable-expansion buffer. |
| `psqlscan_select_top_buffer` | :143 | Re-point flex at the top stacked buffer. |
| `psqlscan_var_is_current_source` | :144 | Recursion guard: is `varname` already being expanded? |
| `psqlscan_prepare_buffer` | :146 | Wrap a string in a flex buffer (FF-substitution for unsafe encodings). |
| `psqlscan_emit` | :149 | Emit scanned text, undoing FF-substitution. |
| `psqlscan_extract_substring` | :150 | Pull a substring back out (FF-aware). |
| `psqlscan_escape_variable` / `_test_variable` | :152-155 | Variable-substitution callbacks. |

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
- BEGIN…END block tracking (`:115-125`): `begin_depth` (:120) plus **two** 4-slot
  identifier windows — `init_idents_count`/`init_idents[4]` (:121-122, identifiers since
  start of statement) and `sub_idents_count`/`sub_idents[4]` (:123-125, identifiers since
  start of a CREATE SCHEMA element) — let the lexer avoid ending a query at a semicolon
  inside a function-body `BEGIN … END`. The `sub_*` pair was added by `049b742daad0` so the
  same BEGIN/END detection works for function bodies nested inside `CREATE SCHEMA`. `[from-comment]` (:115-125)

## Invariants & gotchas

- The standalone-compile typedefs (`:54-55`) must **not** be in scope when the file is included
  from a real `.l` body — there the flex-generated definitions win. The `#ifndef` guard plus
  flex's own include ordering keep them from colliding. `[from-comment]` (:49-53)
- `start_state` is "adopted by yylex() on entry and updated on exit" (`:105-110`) — the lexer's
  start condition persists across input lines until `psql_scan_reset`. Forgetting to reset
  leaves quote/comment nesting state dangling between statements. `[from-comment]` (:105-110)

## Invariants & gotchas — BEGIN/END heuristic

- `init_idents[4]` (`:122`) and `sub_idents[4]` (`:125`) each record only the **first few**
  identifiers — of the statement, and of the current CREATE SCHEMA element respectively — to
  guess whether a `BEGIN` opens a transaction vs a PL block. A fixed 4-slot buffer is a
  heuristic, not a parser — it can misclassify unusual statement shapes. `049b742daad0`
  added the `sub_idents` window precisely because the single statement-level window
  misfired on BEGIN/END inside `CREATE SCHEMA`; the second window narrows but does not
  eliminate the class. This is the same class of "documented-fragile lexer heuristic" the
  A9 plpgsql sweep flagged (the `pl_gram.y` INTO / integer-FOR / PERFORM heuristics).
  `[verified-by-code]`

## Cross-refs

- Public API: [[knowledge/files/src/include/fe_utils/psqlscan.h]].
- Implementations: `src/fe_utils/psqlscan.l`, `src/bin/psql/psqlscanslash.l` (the A4 sweep
  noted `psqlscan.l` as an uncovered corpus gap).

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: BEGIN/END detection uses fixed 4-identifier windows]**
  `psqlscan_int.h:122,125` — `init_idents[4]` (statement) and `sub_idents[4]` (CREATE SCHEMA
  element) each record only the first few identifiers to decide whether a `BEGIN` is
  transactional or a PL block boundary; a heuristic that can misfire on unusual statement
  prefixes. `049b742daad0` (2026-06) added the `sub_idents` window to fix the CREATE SCHEMA
  case, confirming the single-window form was genuinely fragile. Benign (worst case is a
  mis-split at a semicolon, surfaced as a syntax error to the user), but a known-fragile
  lexer heuristic in the same family as the A9 plpgsql grammar heuristics. Severity `nit`.
  Mirrored to `knowledge/issues/fe_utils.md`.
