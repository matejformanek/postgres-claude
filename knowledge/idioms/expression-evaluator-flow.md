# Expression evaluator flow — ExprState + ExprEvalStep machine

PostgreSQL's expression evaluator turns an Expr parse tree
(`a + b * c WHERE d < 5`) into a **flat program** of
`ExprEvalStep` opcodes that a simple interpreter executes
per tuple. Compared to a tree-walk evaluator, the flat
representation is cache-friendly and JIT-compilable. The
init phase produces the program; the run phase walks it.

Anchors:
- `source/src/backend/executor/execExpr.c:1-15` — design
  overview [verified-by-code]
- `source/src/include/executor/execExpr.h` — opcodes
- `knowledge/data-structures/tupletableslot.md` — slots
  consumed by evaluator
- `knowledge/data-structures/datum-nullabledatum.md` —
  output type
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The two-phase model

[from-comment `execExpr.c:7-11`]

> previously been processed by the parser and planner) into
> an ExprState, using ExecInitExpr() et al. This converts
> the tree into a flat array of ExprEvalSteps, which may be
> thought of as instructions in a program.

Phase 1: **Init**. Walk the Expr tree, emit ExprEvalSteps
into a flat array. Once-per-query.

Phase 2: **Run**. Execute the steps per tuple. Many calls.

The init phase amortizes optimization (constant folding,
short-circuit setup, type-cast wiring) over many run
invocations.

## ExprState — the compiled form

```c
typedef struct ExprState
{
    ExprEvalStep   *steps;       /* program */
    int             steps_len;
    /* ... */
    ExprStateEvalFunc evalfunc;  /* "run" entry point */
    Datum           resvalue;    /* result of last op */
    bool            resnull;
} ExprState;
```

The `evalfunc` field is a function pointer — usually the
default interpreter, but for JIT-compiled expressions it
points at the LLVM-generated native code.

## ExprEvalStep — the opcode struct

```c
typedef struct ExprEvalStep
{
    intptr_t           opcode;      /* EEOP_* */
    Datum             *resvalue;    /* where to write result */
    bool              *resnull;
    union {                         /* per-opcode operands */
        struct { ... } func;        /* opcode-specific */
        struct { ... } var;
        struct { ... } sbsref;
        /* etc. */
    } d;
} ExprEvalStep;
```

The `opcode` is an enum value (EEOP_*) selecting one of
~100 possible operations. The union `d` carries opcode-
specific operands.

## Common opcodes

| Opcode | Meaning |
|---|---|
| `EEOP_DONE_RETURN` | End of program; result is resvalue/resnull |
| `EEOP_DONE_NO_RETURN` | End of program; no return value (e.g., qual-only) |
| `EEOP_INNER_VAR` | Read inner-slot's attribute N |
| `EEOP_OUTER_VAR` | Read outer-slot's attribute N |
| `EEOP_SCAN_VAR` | Read scan-slot's attribute N |
| `EEOP_CONST` | Load a constant |
| `EEOP_FUNCEXPR` | Call a function (slow path) |
| `EEOP_FUNCEXPR_STRICT` | Call a function, NULL in → NULL out |
| `EEOP_BOOLTEST_IS_NULL` | x IS NULL |
| `EEOP_BOOLTEST_IS_TRUE` | x IS TRUE |
| `EEOP_QUAL` | If false, short-circuit out |
| `EEOP_JUMP_IF_NULL` | Branch on null |
| `EEOP_JUMP_IF_NOT_NULL` | Branch on non-null |
| `EEOP_ASSIGN_INNER_VAR` | Write to inner slot |
| `EEOP_AGG_INIT_TRANS` | Aggregation step |

[verified-by-code `execExpr.h:EEOP_*` constants]

The wide opcode set lets the init phase pick specialized
versions — e.g., `EEOP_FUNCEXPR_STRICT` is faster than
generic `EEOP_FUNCEXPR` because it doesn't need per-call
null checking.

## The interpreter — ExecInterpExpr

```c
static Datum
ExecInterpExpr(ExprState *state, ExprContext *econtext, bool *isnull);
```

A simple loop:

```c
for (op = state->steps; ; op++) {
    switch (op->opcode) {
        case EEOP_DONE_RETURN:
            return resvalue;
        case EEOP_INNER_VAR:
            resvalue = inner_slot->tts_values[op->d.var.attnum];
            resnull  = inner_slot->tts_isnull[op->d.var.attnum];
            break;
        case EEOP_CONST:
            resvalue = op->d.constval.value;
            resnull  = op->d.constval.isnull;
            break;
        case EEOP_FUNCEXPR_STRICT:
            /* check all args non-null */
            /* call op->d.func.fn_addr(args) */
            break;
        /* ... ~100 cases ... */
    }
}
```

(abstracted)

The switch is a giant computed-goto on modern compilers
(GCC supports the `&&label` syntax) — extremely fast
dispatch.

## JIT compilation

For long-running queries, the init phase can request **LLVM
JIT compilation** of the ExprState. JIT replaces the
interpreter with native code:

- No dispatch overhead (each opcode becomes inline).
- Constant operands become immediate values.
- Function-call overhead is amortized.

Gates on:
- `jit = on` GUC.
- `jit_above_cost` and `jit_inline_above_cost` GUCs.
- The expression's estimated total cost.

## Setup steps

Some opcodes need preparation that can't be done at run
time. `ExecCreateExprSetupSteps` walks the Expr tree
finding these:

- `ExprSetupInfo` collects required setup.
- The first few program steps initialize per-slot state,
  per-aggregate state, etc.

This is why ExprStates have non-trivial init cost. For
hot-path code that creates many ExprStates, the init cost
can dominate.

## The strict-function optimization

`EEOP_FUNCEXPR_STRICT` is the fast-path for functions
declared `STRICT`:

1. Check each argument's null flag.
2. If any is null, set result-null and skip the call.
3. Otherwise, call.

Saves the per-call null-check the function body would
otherwise do. Most builtin functions are strict; the
optimization pays.

## Common review-time concerns

- **Adding a new opcode** requires implementing both the
  interpreter case AND the JIT path.
- **ExprStates are allocated in per-query memory** —
  long-lived plans need explicit handling.
- **The Var attnum** is the attribute index in the slot's
  TupleDesc, NOT the on-disk position. Account for dropped
  columns.
- **JIT is bounded by costs** — measure before enabling
  in production.
- **Setup steps run once per query**, not per tuple. Don't
  optimize per-tuple speed by adding setup that doesn't
  pay off.

## Invariants

- **[INV-1]** Init produces a flat ExprEvalStep program;
  run interprets / JITs it.
- **[INV-2]** Programs terminate with EEOP_DONE_RETURN or
  EEOP_DONE_NO_RETURN.
- **[INV-3]** Var opcodes index into a TupleTableSlot's
  tts_values/tts_isnull.
- **[INV-4]** JIT replaces the interpreter; cost-gated.
- **[INV-5]** Strict-function opcode is the fast path;
  non-strict is fallback.

## Useful greps

- The opcode list:
  `grep -n 'EEOP_' source/src/include/executor/execExpr.h | head -30`
- The init dispatcher:
  `grep -n 'ExecInitExprRec\|ExecInitFunc' source/src/backend/executor/execExpr.c | head -10`
- JIT compilation:
  `grep -RIn 'llvm_compile_expr\|jit_compile_expr' source/src/backend/jit | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execExpr.c`](../files/src/backend/executor/execExpr.c.md) | 1 | design overview |
| [`src/backend/executor/execExpr.c`](../files/src/backend/executor/execExpr.c.md) | — | init + main interpreter |
| [`src/backend/executor/execExprInterp.c`](../files/src/backend/executor/execExprInterp.c.md) | — | interpreter loop |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | — | opcodes |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)
- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/data-structures/tupletableslot.md` — slots
  consumed by the evaluator.
- `knowledge/data-structures/datum-nullabledatum.md` —
  Datum output.
- `knowledge/data-structures/fmgrinfo.md` — function calls
  use FmgrInfo.
- `.claude/skills/executor-and-planner/SKILL.md` —
  executor + planner skill.
- `source/src/backend/executor/execExpr.c` — init + main
  interpreter.
- `source/src/backend/executor/execExprInterp.c` —
  interpreter loop.
- `source/src/include/executor/execExpr.h` — opcodes.
