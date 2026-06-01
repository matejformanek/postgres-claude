# execExpr.h

- **Source:** `source/src/include/executor/execExpr.h` (924 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Internal interface between `execExpr.c` (compiler) and `execExprInterp.c`
(interpreter), plus declarations for the JIT to share. Three main things:

1. `enum ExprEvalOp` — the **opcode set**.
2. `struct ExprEvalStep` — the per-instruction record.
3. Helper-function prototypes for the complex opcodes that are implemented
   as exported routines (shared with JIT).

## ExprEvalOp opcodes `:66+`

Groupings (with starting line numbers):

- **Terminators** `:69-72`: `EEOP_DONE_RETURN`, `EEOP_DONE_NO_RETURN`.
- **FETCHSOME** `:75-79`: ensure first N attrs of INNER / OUTER / SCAN /
  OLD / NEW slot are deformed. OLD/NEW are for MERGE / DML where two slots
  (pre- and post-image) are simultaneously addressable.
- **VAR / SYSVAR / WHOLEROW** `:82-96`: copy a column / system column /
  full row out of a slot into the step's `resvalue/resnull`.
- **ASSIGN_*_VAR / ASSIGN_TMP / ASSIGN_TMP_MAKE_RO** `:103-112`: store into
  a result slot's `tts_values[i]/tts_isnull[i]`.
- **CONST** `:115` — embed a constant.
- **FUNCEXPR / FUNCEXPR_STRICT / FUNCEXPR_STRICT_1/2 / FUNCEXPR_FUSAGE** `:122-127`
  — call a function via `FunctionCallInvoke`; strict variants short-circuit
  on NULL args; `_1`/`_2` are arity-specialized fast paths.
- **BOOL_AND/OR/NOT_STEP** `:135-145` — short-circuit boolean operators.
- **QUAL** `:148` — implicit-AND qual short-circuit (NULL = false).
- **JUMP / JUMP_IF_NULL / NOT_NULL / NOT_TRUE** `:151-156`.
- **NULLTEST / BOOLTEST** `:159-167+`.
- (and many more: case/when, coercions, array/row construction, fielwesselect,
  subscripting, agg transitions, subplan, JSON, …)

The README of `executor/` describes the design; this header is the
truth-table.

## ExprEvalStep struct

A discriminated union: `opcode` + `resvalue/resnull` (pointers to the
target Datum/null) + a per-op `d.<variant>` payload. Sized to fit in a few
cache lines.

## Exported helpers (called by both interpreter and JIT)

`ExecEvalParamExtern`, `ExecEvalSQLValueFunction`, `ExecEvalCurrentOfExpr`,
`ExecEvalNextValueExpr`, `ExecEvalArrayExpr`, `ExecEvalArrayCoerce`,
`ExecEvalRow`, `ExecEvalMinMax`, `ExecEvalFieldSelect`, `ExecEvalFieldStore`,
`ExecEvalConvertRowtype`, `ExecEvalXmlExpr`, `ExecEvalScalarArrayOp`,
`ExecEvalHashedScalarArrayOp`, `ExecEvalConstraintNotNull`,
`ExecEvalConstraintCheck`, `ExecEvalJsonConstructor`, `ExecEvalJsonIsPredicate`,
`ExecEvalJsonExprPath`, etc.

The JIT (LLVM provider, src/backend/jit/llvm/llvmjit_expr.c) generates
calls to these so it doesn't have to re-codegen each uncommon opcode body.

## Internal flags

`EEO_FLAG_INTERPRETER_INITIALIZED` `:28`, `EEO_FLAG_DIRECT_THREADED` —
recorded in ExprState->flags after first prep.

## Tags

- [verified-by-code] opcode list line numbers, struct shape, exported helper
  set.
- [from-comment] file header purpose.
