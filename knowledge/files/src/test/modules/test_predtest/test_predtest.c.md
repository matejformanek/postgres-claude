---
path: src/test/modules/test_predtest/test_predtest.c
anchor_sha: e18b0cb7344
loc: 246
depth: read
---

# src/test/modules/test_predtest/test_predtest.c

## Purpose

Cross-checks the correctness of the optimizer's predicate-proof functions
(`predicate_implied_by` / `predicate_refuted_by` from `predtest.c`)
against an experimental ground truth. Given a test SELECT that returns
two boolean columns, the function (1) runs the query and tabulates the
3-valued (t/f/n) outcomes, (2) extracts the two target-list expressions
as parse trees, and (3) calls the four proof functions; any "proven"
result that contradicts the observed table fires a `WARNING`.
`[verified-by-code]` `test_predtest.c:26-28`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_predtest(query text) returns record` | `:32` | Returns 8 booleans: the four proof outputs (`strong/weak × implied/refuted`) plus the four observed-truth bits (`s_i_holds`, `w_i_holds`, `s_r_holds`, `w_r_holds`) |

## Internal landmarks

- SPI driver (`:57-72`) — `SPI_prepare` + `SPI_execute_plan(read_only)`,
  asserts the query returns exactly two boolean columns.
- 3-value bookkeeping (`:78-118`) — iterates SPI tuples, encoding each
  value as `'t' / 'f' / 'n'`, then for each combination updates the four
  `*_holds` flags. The proof definitions:
  - **strong implication**: `c2 == 't' && c1 != 't'` breaks it (`:107`).
  - **weak implication**: `c2 != 'f' && c1 == 'f'` breaks it (`:110`).
  - **strong refutation**: `c2 == 't' && c1 != 'f'` breaks it (`:113`).
  - **weak refutation**: `c2 == 't' && c1 == 't'` breaks it (`:116`).
- Plan extraction (`:140-150`) — `SPI_plan_get_cached_plan`, then dig
  out the two target-list expressions; asserts exactly one
  `PlannedStmt` of `CMD_SELECT`.
- `make_ands_implicit` (`:166-167`) — applied because target-list exprs
  bypass the normal `canonicalize_qual` /  `make_ands_implicit` step.
  `canonicalize_qual` is **not** applied because it's unclear whether to
  treat the expressions as WHERE or CHECK clauses
  `[from-comment]` `:152-159`.
- Proof calls (`:169-183`) — invokes `predicate_implied_by` /
  `predicate_refuted_by` in both strong (`false`) and weak (`true`)
  modes.
- Internal consistency assertion (`:133`, `:207`) — `s_r_holds` must
  imply `w_r_holds`, both for observed bits and for proven bits;
  violations fire WARNING. The comment notes implication has no
  comparable assertion because moving from strong to weak expands the
  allowed value set `[from-comment]` `:120-132,201-204`.

## Invariants & gotchas

- TEST MODULE — only useful for regression-testing the proof code.
- Query text must produce exactly 2 BOOL columns and contain exactly 1
  statement (`:73-77,142-146`).
- Proof code ignoring RestrictInfo nodes is acknowledged but considered
  acceptable for the test `[from-comment]` `:161-165`.
- WARNING (not ERROR) is used for proof violations so a whole test file
  can run to completion and surface every disagreement, not just the
  first.

## Cross-refs

- `source/src/backend/optimizer/util/predtest.c` — the implementation
  under test.
- `source/src/include/optimizer/optimizer.h` — `predicate_implied_by`,
  `predicate_refuted_by` declarations.
- `knowledge/subsystems/executor-and-planner.md` — overview of predicate
  proofs in qual simplification.
