# execExprInterp.c

- **Source:** `source/src/backend/executor/execExprInterp.c` (5990 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (the hot path; dispatch model + fast paths)

## Purpose

The **interpreter** for ExprState step lists. Implements either "direct
threaded" dispatch (computed gotos, gcc/clang) or "switch threaded" (portable
C) execution of the flat `ExprEvalStep[]` produced by `execExpr.c`.
[from-comment] `:3-46`

## Dispatch model

- `HAVE_COMPUTED_GOTO` → `EEO_USE_COMPUTED_GOTO` → `EEO_DISPATCH` becomes
  `goto *(op->opcode)` after `ExecReadyInterpretedExpr` rewrites each step's
  `opcode` field to the label address. `EEO_FLAG_DIRECT_THREADED` is set on
  the ExprState so we don't redo this. `:90-93, 273-279`
- Without computed gotos, `EEO_SWITCH/EEO_CASE/EEO_DISPATCH` become a plain
  `switch (op->opcode)` inside `ExecInterpExpr`. The same source file is
  re-included with a different EEO_USE_*-symbol setting to materialize both
  variants. `:95-105` (see EEO_CASE definitions)
- The principal worker is `ExecInterpExpr(ExprState*, ExprContext*, bool *isnull)`
  `:470` — a single function with all opcode implementations inlined; this is
  the function the README calls "the fast-path of expression execution"
  (≈1800 lines of opcode bodies).

## Fast-path ExecJust* routines

`ExecReadyInterpretedExpr` `:252` looks at the first ~5 opcodes in a freshly
compiled program and, if the pattern matches a common idiom, sets
`state->evalfunc_private` to a hard-coded routine that bypasses dispatch
entirely. These pay off because the full interpreter's setup cost is
measurable for trivial expressions. [from-comment] `:288-292`

Matched patterns and their handlers (see `:293-470`):

| Pattern | Handler |
| --- | --- |
| just one Var → ExecJustInner/Outer/ScanVar `:2573-2592`, *VarVirt variants `:2711-2728` (no FETCHSOME for virtual slots) |
| just `ASSIGN_*_VAR` → ExecJustAssign* `:2620-2638` (single-Var TLIST copy) |
| OpExpr that's a function of one CaseTestExpr → ExecJustApplyFuncToCase `:2641` |
| a single Const → ExecJustConst `:2679` |
| a Hash-key extraction of a Var → ExecJustHashInner/OuterVar(WithIV) `:2777-2898` (used by HashAgg/Memoize/Hashjoin) |

These ExecJust* are precisely the routines you see show up at the top of
`perf` profiles on OLTP workloads.

## Re-validation entry: `ExecInterpExprStillValid` `:2297`

First-call wrapper installed by `ExecReadyInterpretedExpr`. Calls
`CheckExprStillValid` `:2317` which verifies that the `varattno` of every
`EEOP_*_VAR` step still matches the slot's TupleDesc (schema may have changed
between prepare and execute via plancache). On success it replaces evalfunc
with the real `ExecInterpExpr` for all future calls. [verified-by-code]
`:2317-2406`

## ScalarArrayOpExpr hash table

For `x = ANY(ARRAY[...])` with an all-Const RHS, the compiler can emit a
hashed lookup. `:215-246` defines `ScalarArrayOpExprHashTable` + simplehash
specialization (`saophash`). At runtime EEOP_HASHED_SCALARARRAYOP builds the
table lazily on first call and reuses it for the rest of the scan. Performance
win over linear search becomes large for big IN-lists.

## Helper functions exported for JIT

Per the file header `:42-46`, complex opcode bodies are implemented as
exported helpers (e.g. `ExecEvalParamExtern`, `ExecEvalSQLValueFunction`,
`ExecEvalArrayExpr`, `ExecEvalFieldStore`, `ExecEvalConvertRowtype`,
`ExecEvalArrayCoerce`, `ExecEvalRow`, `ExecEvalMinMax`, `ExecEvalXmlExpr`,
`ExecEvalJsonConstructor`, `ExecEvalJsonExprPath`, …). The JIT (LLVM)
emits direct calls to these so it doesn't have to re-codegen every uncommon
opcode body. **The invariant the README states:** these helpers **must not
dispatch to the next step** — they return, and the caller (interp or JIT)
performs dispatch. [from-README] / `:206-215`

## Notable opcodes worth knowing by name

- `EEOP_DONE_RETURN` vs `EEOP_DONE_NO_RETURN` — terminator differs depending
  on whether the program produces a value (the return is via the ExprState's
  resvalue/resnull) or only side-effects (projection/agg transition).
- `EEOP_QUAL` — the implicit-AND short-circuit used by ExecQual; treats NULL
  as false and jumps to jumpdone on first false.
- `EEOP_JUMP_IF_NULL/_NOT_NULL/_NOT_TRUE` — Boolean short-circuit operators.
- `EEOP_NULLTEST_*` — IS [NOT] NULL with rowtype handling for composite types
  (any field NULL → IS NULL).
- `EEOP_FUNCEXPR_STRICT` — short-circuit a strict function if any arg is NULL.
- `EEOP_AGG_*` — transition value updates inlined into the per-row driver
  ExprState built by `ExecBuildAggTrans`.

## Tags

- [verified-by-code] dispatch model, ExecJust pattern matching, hash specialization.
- [from-comment] file header about JIT-shared helpers and direct-threading.
- [from-README] expression-evaluation invariants.
