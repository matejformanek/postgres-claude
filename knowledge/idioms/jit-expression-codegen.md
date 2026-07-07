# JIT expression codegen — opcode-by-opcode IR generation with one BB per step

`llvmjit_expr.c` turns an `ExprState`'s array of `ExprEvalStep`s
(the same `EEOP_*` opcodes the interpreter switches on in
`execExprInterp.c`) into a native LLVM function. The strategy is
**one LLVM basic block per `EEOP_*` step**, with the function's
control flow mirroring the interpreter's `step.opcode` switch
— but with each opcode's generic dispatch replaced by inlined,
type-specialized IR.

The win over the interpreter:

- **No `step->opcode` switch overhead** — each opcode's
  implementation is just IR in its own basic block; control flow
  is direct (`LLVMBuildBr`).
- **Constants are baked in** — `FmgrInfo *finfo` pointers,
  `ScalarArrayOpExpr.useOr`, attribute numbers, etc. become
  `LLVMConstInt`/`LLVMConstIntToPtr` immediates in the IR. The
  optimizer can constant-fold their consumers.
- **Type specialization** — `pg_proc.proretset = false` aggregates
  collapse to a single non-set-returning code path.
- **Cross-module inlining** of fmgr callees (see
  [[jit-tuple-deform-and-inline]]).

This doc walks the function signature, the preamble (loading
ExprContext slot/values/nulls into LLVM SSA registers), the
per-opcode `switch (opcode)` that emits IR per step, the
basic-block-per-step structure, an opcode walkthrough
(`EEOP_FUNCEXPR_STRICT`), and how the JIT'd function returns to
the interpreter for unsupported opcodes.

Companion docs:
- [[jit-provider-and-context]] — the JitContext + lazy-emit lifecycle.
- [[jit-tuple-deform-and-inline]] — specialized deform + fmgr inline.
- [[expression-evaluator-flow]] — the `EEOP_*` interpreter this mirrors.

## Anchors

- `source/src/backend/jit/llvm/llvmjit_expr.c:1-78` — banner + helper macros.
- `source/src/backend/jit/llvm/llvmjit_expr.c:80-320` — `llvm_compile_expr` preamble.
- `source/src/backend/jit/llvm/llvmjit_expr.c:321-2000+` — the per-opcode switch.
- `source/src/backend/jit/llvm/llvmjit_expr.c:666-755` — `EEOP_FUNCEXPR_STRICT*` example.
- `source/src/backend/executor/execExpr.c` — `ExecBuildAggTrans` etc. (the producer of the ExprState).
- `source/src/backend/executor/execExprInterp.c` — the interpreter, opcode-by-opcode.
- `source/src/include/executor/execExpr.h` — `EEOP_*` enum + `ExprEvalStep` struct.
- `source/src/include/jit/llvmjit.h` — `Struct*` LLVM type refs and `Attribute*` templates.

## The function signature

Every JIT'd expression has the same C-level signature:

```c
Datum ExecInterpExpr(ExprState *state, ExprContext *econtext, bool *isnull);
```

This matches `ExprStateEvalFunc`. The JIT'd function lives in an
LLVM module under the name `evalexpr_<counter>`, with attributes
copied from a template (`AttributeTemplate`) so it matches
calling-convention details (sysv ABI, no-throw, etc.).

`llvm_pg_var_func_type("ExecInterpExprStillValid")` returns the
function type pointer — the JIT'd function is type-identical to
the existing C function `ExecInterpExprStillValid` (the
"interpreter-restart" thunk used for stand-alone exprs). The
existing interpreter remains the fallback for opcodes JIT doesn't
support yet.

[verified-by-code] (`llvmjit_expr.c:164-168`).

## The preamble — loading state into LLVM SSA

The preamble (lines 156-300) does the equivalent of the
interpreter's "load state pointers into local variables at function
entry":

```c
/* Get function parameters */
v_state    = LLVMGetParam(eval_fn, 0);   /* ExprState *state */
v_econtext = LLVMGetParam(eval_fn, 1);   /* ExprContext *econtext */
v_isnullp  = LLVMGetParam(eval_fn, 2);   /* bool *isnull */

/* Load state->resvalue, state->resnull pointers (struct GEP) */
v_tmpvaluep  = l_struct_gep(b, StructExprState, v_state,
                            FIELDNO_EXPRSTATE_RESVALUE, ...);
v_tmpisnullp = l_struct_gep(b, StructExprState, v_state,
                            FIELDNO_EXPRSTATE_RESNULL, ...);
v_parent     = l_load_struct_gep(b, StructExprState, v_state,
                                 FIELDNO_EXPRSTATE_PARENT, ...);

/* Load econtext->{scantuple,innertuple,outertuple,oldtuple,newtuple} slots */
v_scanslot   = l_load_struct_gep(b, StructExprContext, v_econtext,
                                 FIELDNO_EXPRCONTEXT_SCANTUPLE, ...);
v_innerslot  = ...; v_outerslot = ...; v_oldslot = ...; v_newslot = ...;

/* Load slot->tts_values and slot->tts_isnull arrays */
v_scanvalues  = l_load_struct_gep(b, StructTupleTableSlot, v_scanslot,
                                  FIELDNO_TUPLETABLESLOT_VALUES, ...);
v_scannulls   = l_load_struct_gep(b, StructTupleTableSlot, v_scanslot,
                                  FIELDNO_TUPLETABLESLOT_ISNULL, ...);
... (same for inner/outer/old/new/result)

/* Load econtext->ecxt_aggvalues / ecxt_aggnulls */
v_aggvalues = l_load_struct_gep(b, StructExprContext, v_econtext,
                                FIELDNO_EXPRCONTEXT_AGGVALUES, ...);
v_aggnulls  = l_load_struct_gep(b, StructExprContext, v_econtext,
                                FIELDNO_EXPRCONTEXT_AGGNULLS, ...);
```

[verified-by-code] (`llvmjit_expr.c:172-300`).

The `StructXxx` type references come from `llvmjit_types.c`, which
exposes Postgres's C struct layouts to LLVM. The
`FIELDNO_XXX_YYY` constants are autogenerated from a separate
.c file that LLVM compiles to bitcode, ensuring the field offsets
the JIT uses match what the C compiler produces.

This "load everything upfront, then never reload" pattern lets
LLVM's register allocator keep these pointers in registers across
the entire function. The interpreter does the same (local C
variables), but the JIT'd version skips the interpreter's
per-step `step->opcode` switch entirely.

## Basic block per step — the control-flow skeleton

```c
/* llvmjit_expr.c:301-307 */
opblocks = palloc_array(LLVMBasicBlockRef, state->steps_len);
for (int opno = 0; opno < state->steps_len; opno++)
    opblocks[opno] = l_bb_append_v(eval_fn, "b.op.%d.start", opno);

LLVMBuildBr(b, opblocks[0]);    /* entry → first op */
```

[verified-by-code] (`llvmjit_expr.c:301-307`).

Then the main loop emits IR for each step:

```c
for (int opno = 0; opno < state->steps_len; opno++)
{
    ExprEvalStep *op = &state->steps[opno];
    LLVMOpcode  opcode = op->opcode;

    LLVMPositionBuilderAtEnd(b, opblocks[opno]);

    switch (opcode) {
    case EEOP_DONE_RETURN:           ...; break;
    case EEOP_DONE_NO_RETURN:        ...; break;
    case EEOP_INNER_FETCHSOME:       ...; break;
    case EEOP_OUTER_FETCHSOME:       ...; break;
    case EEOP_SCAN_FETCHSOME:        ...; break;
    case EEOP_INNER_VAR:             ...; break;
    case EEOP_OUTER_VAR:             ...; break;
    case EEOP_SCAN_VAR:              ...; break;
    case EEOP_INNER_SYSVAR: ...;
    case EEOP_FUNCEXPR_STRICT:       ...; break;
    case EEOP_BOOL_AND_STEP_FIRST:   ...; break;
    case EEOP_JUMP:                  ...; break;
    case EEOP_AGG_PLAIN_TRANS_BYVAL: ...; break;
    case EEOP_AGG_PLAIN_TRANS_STRICT_BYREF: ...; break;
    ...

    default:
        /* Not implemented — fall back to interpreter for this op */
        build_EvalXFunc(b, mod, "ExecEvalStepNoReturn", v_state, op, opcode);
        LLVMBuildBr(b, opblocks[opno + 1]);   /* continue to next op */
        break;
    }
}
```

[verified-by-code] (`llvmjit_expr.c:321-2000+`).

Each `case` emits IR that:

1. Does the opcode's work (loads, compares, calls fmgr functions).
2. Branches to `opblocks[opno + 1]` to continue (or to some other
   block for control-flow opcodes like `EEOP_JUMP` /
   `EEOP_BOOL_AND_STEP`).

**Default branch is critical**: if an opcode isn't handled, we
call `ExecEvalStepNoReturn(state, op)` (a small C wrapper that
runs the interpreter's single-step logic), then branch to the
next opblock. So JIT'd functions can have a mix of native IR and
interpreter-callback steps — partial coverage works, no need to
implement every opcode.

## Example: `EEOP_FUNCEXPR_STRICT`

```c
/* llvmjit_expr.c:666-755 (paraphrased) */
case EEOP_FUNCEXPR_STRICT:
case EEOP_FUNCEXPR_STRICT_1:
case EEOP_FUNCEXPR_STRICT_2:
{
    FunctionCallInfo fcinfo = op->d.func.fcinfo_data;
    LLVMValueRef v_fcinfo = l_ptr_const(fcinfo, l_ptr(StructFunctionCallInfoData));

    /* For each argument, build a basic block that checks args[i].isnull */
    LLVMBasicBlockRef b_checkargnulls[FUNC_MAX_ARGS];
    LLVMBasicBlockRef b_call = l_bb_append_v(eval_fn, ...);
    LLVMBasicBlockRef b_isnull = l_bb_append_v(eval_fn, ...);

    /* Each b_checkargnulls[i] either branches to b_isnull (any null → result null)
       or to the next arg check / b_call */
    LLVMBuildBr(b, b_checkargnulls[0]);

    for (int i = 0; i < nargs; i++) {
        LLVMPositionBuilderAtEnd(b, b_checkargnulls[i]);
        v_arg_isnull = LLVMBuildLoad2(b, ..., load fcinfo->args[i].isnull, ...);
        is_null_cmp = LLVMBuildICmp(b, LLVMIntEQ, v_arg_isnull, 1);
        if (i == nargs - 1)
            LLVMBuildCondBr(b, is_null_cmp, b_isnull, b_call);
        else
            LLVMBuildCondBr(b, is_null_cmp, b_isnull, b_checkargnulls[i + 1]);
    }

    /* b_isnull: store null in result */
    LLVMPositionBuilderAtEnd(b, b_isnull);
    LLVMBuildStore(b, l_int8_const(1), v_resnullp);
    LLVMBuildBr(b, opblocks[opno + 1]);

    /* b_call: actually invoke the function */
    LLVMPositionBuilderAtEnd(b, b_call);
    v_fn_addr = llvm_function_reference(context, b, mod, fcinfo);  /* may inline */
    v_retval = LLVMBuildCall2(b, ..., v_fn_addr, args = {v_fcinfo}, ...);
    LLVMBuildStore(b, v_retval, v_resvaluep);
    /* Load fcinfo->isnull → resnull */
    LLVMBuildStore(b, l_load_struct_gep(..., FUNCINFO_ISNULL, ...), v_resnullp);

    LLVMBuildBr(b, opblocks[opno + 1]);
}
```

[verified-by-code] (`llvmjit_expr.c:666-755`).

Three nested CFG branches:

1. **Per-argument null check chain**: each arg has its own
   block; nulls cause early jump to `b_isnull`. All-non-null
   falls through to `b_call`.
2. **`b_isnull`**: store NULL result, branch to next op.
3. **`b_call`**: invoke the function, store result+isnull, branch
   to next op.

The crucial `llvm_function_reference` call (line ~720) is where
**cross-module inlining** happens (when `PGJIT_INLINE` is on):
the function reference can resolve to a function in another LLVM
module that gets pulled into the current one and inlined into
the call site. See [[jit-tuple-deform-and-inline]].

## The `EEOP_*_FETCHSOME` opcodes — deform integration

The expression evaluator's tuple-deform steps
(`EEOP_INNER_FETCHSOME`, `EEOP_OUTER_FETCHSOME`,
`EEOP_SCAN_FETCHSOME`) are a special case: each can be JIT'd with
a **specialized deform function** that knows the exact attribute
layout. See [[jit-tuple-deform-and-inline]] for the deform-specific
codegen path.

## Optimization opportunity — constant folding

The expression interpreter does the same work, but with
indirections. After JIT, LLVM's optimizer (when `PGJIT_OPT3` is
set) sees:

```llvm
%fn = inttoptr i64 0x7f1234567890 to ptr               ; FmgrInfo *
%v0 = load i64, ptr %values, align 8                   ; values[0]
%n0 = load i8, ptr %nulls, align 1                     ; nulls[0]
%isnull = icmp eq i8 %n0, 1
br i1 %isnull, label %b_isnull, label %b_call
b_call:
  store i64 %v0, ptr %fcinfo.args[0].value
  ...
  %result = call i64 @some_pg_function(ptr %fcinfo)
```

LLVM's optimizer can:

- Constant-fold the `inttoptr` (the FmgrInfo address is a
  literal constant in the IR).
- Inline the call when `PGJIT_INLINE` is set and the callee's
  bitcode is available.
- Eliminate redundant null checks (e.g. if `EEOP_INNER_VAR`
  already loaded the same arg's null flag earlier).
- SROA / mem2reg the local FunctionCallInfo struct, eliminating
  spills to memory.

These optimizations are why `jit_optimize_above_cost` exists as
a separate gate — the wins are huge for hot expressions, but the
optimize passes themselves cost ~50 ms or more.

## Generating fresh names

The function name has to be unique within the module + the
backend's lifetime (since Orc JIT looks up by name). The
`llvm_expand_funcname` helper combines:

```
<context_id>_<module_generation>_<counter>_<basename>
```

`context_id` is per-LLVMJitContext, `module_generation`
increments per module within a context, `counter` is per-name
within a module. Collisions are statistically impossible.

[verified-by-code] (`llvmjit.c:342`).

## Stub registration with the executor

After `llvm_compile_expr` returns true, the caller (`ExecInitExpr`
etc.) sets:

```c
state->evalfunc = (ExprStateEvalFunc) ExecCompileExpr;
```

where `ExecCompileExpr` is the "compile-on-first-call" stub:

```c
static Datum ExecCompileExpr(ExprState *state, ExprContext *econtext, bool *isnull)
{
    /* First call: ask provider to finalize the module */
    void *func = llvm_get_function(...);
    state->evalfunc = func;
    return ((ExprStateEvalFunc) func)(state, econtext, isnull);
}
```

This is what triggers `llvm_compile_module` on demand. Subsequent
calls hit the native function directly. [verified-by-code]
(`llvmjit_expr.c` ends with this stub registration; see
`execExpr.c`'s use of `ExecReadyExpr`).

## Memory contexts and ResourceOwner integration

The JIT'd functions live in **JIT-allocated memory** (managed by
`SectionMemoryManager`), not in any Postgres memory context.
Cleanup is via ResourceOwner: at xact end (or error),
`ResourceOwnerRelease` invokes
`ResOwnerReleaseJIT → jit_release_context`, which calls
`llvm_release_context` which iterates `context->handles` and
tells Orc JIT to drop each.

The LLVM IR build proceeds in normal Postgres memory (palloc'd
via `palloc_array` for `opblocks[]` etc.); LLVM internal data
structures live in `LLVMContextRef`-managed memory.

## Per-opcode coverage status

The expression interpreter has 100+ `EEOP_*` opcodes. `llvmjit_expr.c`
implements **most common ones natively** — variables, common
function calls, BOOL/AND/OR step combinations, parameters, jumps,
aggregate transitions, FieldStore, RowExpr, ArrayExpr, ScalarArrayOp,
case expressions. Less-common opcodes (XML expressions, certain
domain ops, SQLValueFunction) fall back to the interpreter step
function via the default case.

To check coverage for a specific opcode: grep for `case EEOP_FOO`
in `llvmjit_expr.c`. If absent, it falls back. Adding native
codegen for a new opcode is a recurring contribution pattern in
PG development.

## Invariants and races

1. **Function signature is fixed**: `(ExprState *, ExprContext *,
   bool *) → Datum`. Matches interpreter.
2. **One basic block per opcode step** — control flow mirrors the
   step index. `opblocks[opno + 1]` is the natural fallthrough.
3. **Each opcode's IR runs entirely in its basic block** — no
   cross-block IR fragments. Branches happen at block end.
4. **Default fallback to interpreter** for unhandled opcodes
   means partial coverage is safe.
5. **Constants from ExprEvalStep are baked into IR** as
   `LLVMConstInt`/`LLVMConstIntToPtr` — letting LLVM's optimizer
   see them. [verified-by-code] (`l_ptr_const`, `LLVMConstInt`
   usage throughout).
6. **Slots and value/null arrays are loaded once at function
   entry** — LLVM register-allocates them across the function.
7. **Cross-module inlining is opt-in via `PGJIT_INLINE`**; without
   it, `llvm_function_reference` returns an external function
   declaration that the linker resolves at emit time.
8. **The LLVMBuilder's "current insertion point"** is a stateful
   field; every IR emission moves it. `LLVMPositionBuilderAtEnd`
   resets to the end of a specific block. [verified-by-code]
   (use of `LLVMPositionBuilderAtEnd` throughout).
9. **`AttributeTemplate`** in `llvmjit_types.c` carries function
   attributes (calling convention, no-throw, etc.) that the new
   `eval_fn` copies via `llvm_copy_attributes`. Critical for ABI
   compatibility.
10. **`l_struct_gep` (load via GEP)** generates struct-field
    accesses using the `Struct*` LLVM types in `llvmjit.h`. The
    field numbers (`FIELDNO_*`) are autogenerated to stay in
    sync with C struct layouts.

## Useful greps

```bash
# Top-level entry:
grep -n "^llvm_compile_expr\b" source/src/backend/jit/llvm/llvmjit_expr.c

# Opcode dispatch switch:
grep -nE "case EEOP_" source/src/backend/jit/llvm/llvmjit_expr.c | head -40

# Fallback path:
grep -n "ExecEvalStepNoReturn\|build_EvalXFunc" source/src/backend/jit/llvm/llvmjit_expr.c

# Cross-module function-reference resolution:
grep -n "^llvm_function_reference\b" source/src/backend/jit/llvm/llvmjit.c

# Struct field numbers (autogenerated):
grep "FIELDNO_" source/src/backend/jit/llvm/llvmjit_expr.c | head -20

# Helper macros (l_struct_gep, l_bb_append_v, l_ptr_const):
grep -n "#define l_\|static inline.*l_struct_gep\|l_bb_append" \
       source/src/backend/jit/llvm/llvmjit_emit.h
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execExpr.c`](../files/src/backend/executor/execExpr.c.md) | — | ExecBuildAggTrans etc. (the producer of the ExprState) |
| [`src/backend/executor/execExprInterp.c`](../files/src/backend/executor/execExprInterp.c.md) | — | interpreter, opcode-by-opcode |
| [`src/backend/jit/llvm/llvmjit_expr.c`](../files/src/backend/jit/llvm/llvmjit_expr.c.md) | 1 | banner + helper macros |
| [`src/backend/jit/llvm/llvmjit_expr.c`](../files/src/backend/jit/llvm/llvmjit_expr.c.md) | 80 | llvm_compile_expr preamble |
| [`src/backend/jit/llvm/llvmjit_expr.c`](../files/src/backend/jit/llvm/llvmjit_expr.c.md) | 321 | 2000+ — the per-opcode switch |
| [`src/backend/jit/llvm/llvmjit_expr.c`](../files/src/backend/jit/llvm/llvmjit_expr.c.md) | 666 | EEOP_FUNCEXPR_STRICT example |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | — | EEOP_ enum + ExprEvalStep struct |
| [`src/include/jit/llvmjit.h`](../files/src/include/jit/llvmjit.h.md) | — | Struct LLVM type refs and Attribute templates |

<!-- /callsites:auto -->

## Cross-references

- [[jit-provider-and-context]] — JitContext lifecycle + lazy emit.
- [[jit-tuple-deform-and-inline]] — `EEOP_INNER_FETCHSOME` codegen and `llvm_function_reference` inlining.
- [[expression-evaluator-flow]] — `EEOP_*` interpreter being mirrored.
- [[aggregate-hash-vs-sort]] — `ExecBuildAggTrans` mega-expression is the prime JIT target.
- `source/src/backend/executor/execExprInterp.c` — the interpreter side.
- `source/src/include/executor/execExpr.h` — opcode definitions.
