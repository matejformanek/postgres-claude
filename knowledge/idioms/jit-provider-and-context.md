# JIT — provider model, JitContext lifecycle, and the cost-gated three-stage GUC ladder

PostgreSQL's JIT subsystem is a **provider-loaded** facility: the
core `jit.c` ships only a thin dispatcher and never links against
LLVM. A pluggable shared library (`llvmjit.so` currently the only
shipped provider) is dlopened on first use, registers callbacks via
`_PG_jit_provider_init`, and handles all the heavy LLVM IR
generation. Backends that never JIT never load LLVM — important for
embedded/constrained environments.

The planner decides per-query whether to JIT using a **three-stage
cost ladder**: `jit_above_cost` (do anything), `jit_inline_above_cost`
(also do cross-module inlining of fmgr callees), `jit_optimize_above_cost`
(also run LLVM's `-O3` passes). Each Plan carries the resulting
`jitFlags` (`PGJIT_*` bits) into execution time, where `jit_compile_expr`
consults them per ExprState.

This doc covers the provider-loading dance, the `JitContext` /
`LLVMJitContext` lifecycle and resource-owner integration, the
planner's cost gates, the `PGJIT_*` flag bits, the lazy-emit
behavior (modules built up across many `compile_expr` calls before
a single optimize+emit pass), and the LLVMContext reuse-with-reset
strategy that bounds memory growth.

Companion docs:
- [[jit-expression-codegen]] — IR generation from `EEOP_*` ops.
- [[jit-tuple-deform-and-inline]] — specialized deform + cross-module fmgr inlining.

## Anchors

- `source/src/backend/jit/README` — design overview (~250 lines).
- `source/src/backend/jit/jit.c:1-191` — entire core; tiny + complete.
- `source/src/include/jit/jit.h:19-24` — `PGJIT_*` flag bits.
- `source/src/include/jit/jit.h:27-46` — `JitInstrumentation`.
- `source/src/include/jit/jit.h:57-79` — `JitContext` + `JitProviderCallbacks`.
- `source/src/include/jit/llvmjit.h:43-71` — `LLVMJitContext` extending `JitContext`.
- `source/src/backend/optimizer/plan/planner.c:703-727` — cost-gate logic.
- `source/src/backend/jit/llvm/llvmjit.c:150-260` — `llvm_create_context`, callback registration.
- `source/src/backend/jit/llvm/llvmjit.c:317-380` — `llvm_mutable_module`, `llvm_get_function` (lazy emit).
- `source/src/backend/jit/llvm/llvmjit.c:604-933` — `llvm_optimize_module`, `llvm_compile_module`.

## The provider model

`jit.c` is **provider-agnostic**. It defines a callback struct
populated by the loaded provider:

```c
/* jit.h:74-79 */
struct JitProviderCallbacks {
    JitProviderResetAfterErrorCB    reset_after_error;
    JitProviderReleaseContextCB     release_context;
    JitProviderCompileExprCB        compile_expr;
};
```

Loading flow (`jit.c:67-121`):

```c
static bool provider_init(void) {
    if (!jit_enabled) return false;
    if (provider_failed_loading)     return false;
    if (provider_successfully_loaded) return true;

    /* Check shared library exists before dlopen — avoids ereport */
    snprintf(path, "%s/%s%s", pkglib_path, jit_provider, DLSUFFIX);
    if (!pg_file_exists(path)) {
        provider_failed_loading = true;
        return false;
    }

    /* Mark failed FIRST, in case load_external_function() errors */
    provider_failed_loading = true;

    init = (JitProviderInit) load_external_function(path, "_PG_jit_provider_init", true, NULL);
    init(&provider);

    provider_successfully_loaded = true;
    provider_failed_loading = false;
    return true;
}
```

[verified-by-code] (`jit.c:67-121`).

The "mark failed first" trick (line 108) is for crash safety:
`load_external_function` may `ereport(ERROR)` if dependencies are
missing (e.g. libLLVM not installed). The error propagates up,
but the next call sees `provider_failed_loading = true` and
short-circuits without re-trying.

The default provider is `llvmjit`. To swap: `jit_provider =
'myprovider'` (must exist at `$pkglib_path/myprovider.so` and
expose `_PG_jit_provider_init`).

## The cost gates — three GUCs setting three flags

```c
/* planner.c:703-727 (paraphrased) */
result->jitFlags = PGJIT_NONE;
if (jit_enabled && jit_above_cost >= 0 && top_plan->total_cost > jit_above_cost)
{
    result->jitFlags |= PGJIT_PERFORM;

    if (jit_optimize_above_cost >= 0 && total_cost > jit_optimize_above_cost)
        result->jitFlags |= PGJIT_OPT3;
    if (jit_inline_above_cost >= 0 && total_cost > jit_inline_above_cost)
        result->jitFlags |= PGJIT_INLINE;

    if (jit_expressions)
        result->jitFlags |= PGJIT_EXPR;
    if (jit_tuple_deforming)
        result->jitFlags |= PGJIT_DEFORM;
}
```

[verified-by-code] (`planner.c:703-727`).

Five bits in `PGJIT_*`:

| Flag             | Bit | Meaning                                     | Default GUC                                 |
|------------------|-----|---------------------------------------------|---------------------------------------------|
| `PGJIT_PERFORM`  | 0x01 | Do any JIT at all                            | `jit_above_cost > 0` (default 100000)       |
| `PGJIT_OPT3`     | 0x02 | Apply LLVM `-O3` (expensive)                 | `jit_optimize_above_cost > 0` (500000)      |
| `PGJIT_INLINE`   | 0x04 | Cross-module inlining of fmgr callees        | `jit_inline_above_cost > 0` (500000)        |
| `PGJIT_EXPR`     | 0x08 | JIT-compile expressions                      | `jit_expressions = on`                      |
| `PGJIT_DEFORM`   | 0x10 | JIT-compile tuple deforming                  | `jit_tuple_deforming = on`                  |

[verified-by-code] (`jit.h:19-24`).

The cost ladder reflects the **cumulative cost** of JIT itself: a
plan that runs in microseconds doesn't benefit from a 100 ms LLVM
optimize+emit pass; one that runs for 10 seconds amortizes that
cost easily.

The set bits propagate from the planner into the executor via
`PlannedStmt.jitFlags`, then into `EState.es_jit_flags` at
`InitPlan`, then consulted per `ExprState` at
`ExecInitExprWithParams` / `ExecBuildAggTrans` / etc.

## `JitContext` — the lifecycle owner

```c
/* jit.h:57-63 */
typedef struct JitContext {
    int                flags;       /* PGJIT_* */
    JitInstrumentation instr;
} JitContext;

/* llvmjit.h:43-71 — LLVMJitContext extends */
typedef struct LLVMJitContext {
    JitContext      base;
    ResourceOwner   resowner;       /* automatic cleanup on transaction abort */
    size_t          module_generation;   /* used to generate unique names */

    LLVMContextRef  llvm_context;   /* LLVM's per-thread state — reused, reset periodically */
    LLVMModuleRef   module;         /* current module being built */
    bool            compiled;       /* has the current module been finalized? */
    int             counter;        /* fresh-name counter */
    List           *handles;        /* Orc JIT handles for emitted code */
} LLVMJitContext;
```

`JitContext` lives in `EState->es_jit` (one per query). The base
struct just carries the flag set and instrumentation
counters; the LLVM provider adds its own per-context state.

`llvm_create_context` (`llvmjit.c:223`) allocates the context in
`TopMemoryContext`, registers it with the current ResourceOwner
(`ResourceOwnerRememberJIT`), and creates an `LLVMContextRef`.
The ResourceOwner integration is critical: if the query errors
out, ResourceOwnerRelease invokes
`ResOwnerReleaseJIT → jit_release_context` to free the LLVM
module + emitted code. [verified-by-code] (`llvmjit.c:132-145`).

## The lazy-emit pattern

JIT isn't done per-expression — it's done **per query** (or
larger batches). The flow:

```
ExecBuildProjectionInfo / ExecBuildAggTrans / etc.
    │
    └── ExprState constructed
        │
        └── jit_compile_expr(state)
            │
            └── provider.compile_expr(state) = llvm_compile_expr
                │
                └── llvm_mutable_module(context)   ← lazily allocates module
                    Adds new function to module
                    Sets state->evalfunc to a "compile-on-first-call" stub
                    context->compiled = false
```

When the executor later calls `state->evalfunc(...)` for the
first time:

```c
state->evalfunc = ExecCompileExpr;     // initial stub

ExecCompileExpr(...) {
    /* On first call, finalize the module */
    void *fn = llvm_get_function(context, name);
    state->evalfunc = (ExprStateEvalFunc) fn;
    return fn(...);
}
```

`llvm_get_function` (`llvmjit.c:363-380`):

```c
void *llvm_get_function(LLVMJitContext *context, const char *funcname) {
    if (!context->compiled) {
        /* Single optimize+emit pass for all pending functions */
        llvm_compile_module(context);
    }
    /* Resolve in Orc JIT symbol table */
    return (void *) OrcLookupSymbol(funcname);
}
```

[verified-by-code] (`llvmjit.c:363-380`).

The first `llvm_get_function` call triggers `llvm_compile_module`
which:

1. Runs LLVM's optimization passes (level depends on
   `PGJIT_OPT3`).
2. If `PGJIT_INLINE`, runs the custom inliner that pulls in
   external function bitcode (see [[jit-tuple-deform-and-inline]]).
3. Hands the module to LLVM's Orc JIT for code emission.
4. Records the handle in `context->handles`.

Subsequent `llvm_get_function` calls within the same context
hit the Orc symbol table directly.

This **batched emit** lets multiple expressions in one query
share a single emit pass — important because emit-time overhead
is high (LLVM IR → machine code via codegen pipeline).

## Module rotation — bounded LLVMContext memory

LLVM's `LLVMContextRef` accumulates type information across
compilations. Reusing the same context for thousands of queries
would leak memory. The strategy: **rotate the context periodically**.

`llvm_create_context` reuses an existing `LLVMContextRef`
(stored in static `llvm_session_context`) — but
`llvm_compile_module` checks if the context has grown too large
and disposes it, forcing the next `llvm_create_context` to allocate
a fresh one.

[verified-by-code] (`llvmjit.c:166-225`).

The "fresh context every N modules" bounds backend memory usage
even under high-JIT workloads.

## Instrumentation

`JitInstrumentation` (`jit.h:27-46`) carries per-context counters:

```c
typedef struct JitInstrumentation {
    size_t      created_functions;
    instr_time  generation_counter;      /* time to build IR */
    instr_time  deform_counter;          /* time for deform-specific IR */
    instr_time  inlining_counter;        /* time for cross-module inline */
    instr_time  optimization_counter;    /* LLVM passes */
    instr_time  emission_counter;        /* IR → machine code */
} JitInstrumentation;
```

Surfaced via `EXPLAIN ANALYZE`:

```
JIT:
  Functions: 6
  Options: Inlining true, Optimization true, Expressions true, Deforming true
  Timing: Generation 0.5ms, Inlining 8.2ms, Optimization 78.1ms,
          Emission 32.4ms, Total 119.2ms
```

Each parallel worker accumulates its own counters; the leader
aggregates them via `InstrJitAgg` (`jit.c:182-191`) for the
final EXPLAIN output. The `SharedJitInstrumentation` struct
provides the DSM storage for this.

## The error-recovery hook

`jit_reset_after_error` (`jit.c:127-132`) is called from the
postgres backend's main error-recovery path (after
`AbortTransaction`). It tells the provider to reset its own
state — LLVM has internal threads/state that need cleanup
beyond what ResourceOwner does.

In `llvmjit_error.cpp`, this `llvm_reset_after_error` calls
`llvm_leave_fatal_on_oom()` to disable a special OOM handler
that LLVM uses to convert allocation failures into FATAL
errors (since LLVM's own OOM handling uses C++ exceptions,
which can't propagate cleanly through Postgres's longjmp-based
error handling).

## `jit_compile_expr` — the per-Expr entry

```c
/* jit.c:152-179 */
bool jit_compile_expr(struct ExprState *state) {
    /* No parent means standalone expr; can't tie JIT lifetime → skip */
    if (!state->parent) return false;

    if (!(state->parent->state->es_jit_flags & PGJIT_PERFORM))
        return false;
    if (!(state->parent->state->es_jit_flags & PGJIT_EXPR))
        return false;

    if (provider_init())
        return provider.compile_expr(state);

    return false;
}
```

[verified-by-code] (`jit.c:151-179`).

Two gates:

1. **`state->parent`** must be set — i.e. the ExprState belongs
   to a PlanState. Stand-alone expressions (e.g. used in trigger
   evaluations, ALTER TABLE constraint checks) skip JIT because
   there's no PlanState lifetime to attach the JIT to.
2. **`PGJIT_PERFORM | PGJIT_EXPR`** must both be set.

Returns `true` if the expression was JITed (`state->evalfunc`
now points at the compile-on-first-call stub); `false` if not
(interpreter path remains).

## Standalone-expression workaround

The "standalone expression skipped" rule has performance
implications: triggers, CHECK constraints, defaults, etc. don't
benefit from JIT. This is a known limitation; the README discusses
it: storing the JIT context outside any PlanState would tie it to
the transaction lifetime, which can lead to "noticeable memory
usage" plus quadratic slowdowns in gdb (per the source comment).
[from-comment] (`jit.c:152-164`).

## SectionMemoryManager — emit-time memory protection

`SectionMemoryManager.cpp` overrides LLVM's default memory
manager for emitted code. It tracks emit-time pages so they can
be properly released when the JitContext goes away. Without this,
emit-time pages would leak.

[verified-by-code] (`SectionMemoryManager.cpp`).

The Orc JIT (LLVM's ORCv2 JIT engine) calls into this manager
when it allocates code+data sections. Cleanup happens via
`ResourceOwnerRelease → release_context → llvm_release_context`,
which walks `context->handles` and tells Orc to drop each.

## Invariants and races

1. **Provider load is single-shot, cached** via
   `provider_successfully_loaded` / `_failed_loading`. No retry
   on failure. [from-comment] (`jit.c:77-80`).
2. **`jit_above_cost`** is the gate; `jit_inline_above_cost` /
   `jit_optimize_above_cost` are additive on top. Setting any of
   the latter to `-1` disables that stage even if `jit_above_cost`
   is exceeded.
3. **`PGJIT_INLINE` and `PGJIT_OPT3` are independent** — you can
   have one without the other based on cost thresholds.
4. **JIT is per-query**, not per-backend. Each PlannedStmt
   carries its own flag set.
5. **Standalone ExprStates (no parent PlanState) skip JIT** to
   bound memory. [from-comment] (`jit.c:152-164`).
6. **`llvm_get_function` finalizes the entire module** on first
   call — multiple expressions in one query share the emit pass.
7. **`LLVMContextRef` is reused across contexts** but rotated
   when it grows too large.
8. **`reset_after_error` is essential** — LLVM's internal state
   can outlive ResourceOwnerRelease.
9. **`SectionMemoryManager`** manages emit-time code+data pages
   to enable proper cleanup. Custom override of LLVM's default
   memory manager.
10. **Each parallel worker has its own JitContext** — the
    `SharedJitInstrumentation` DSM is just for aggregating
    counters into EXPLAIN output.

## Useful greps

```bash
# Provider model:
grep -n "JitProviderCallbacks\|provider_init\|_PG_jit_provider_init" \
       source/src/backend/jit/jit.c \
       source/src/include/jit/jit.h \
       source/src/backend/jit/llvm/llvmjit.c

# Cost-gate logic:
grep -n "jit_above_cost\|jit_inline_above_cost\|jit_optimize_above_cost\|jitFlags\|es_jit_flags" \
       source/src/backend/optimizer/plan/planner.c \
       source/src/include/jit/jit.h

# PGJIT_* flag check sites:
grep -rn "PGJIT_PERFORM\|PGJIT_EXPR\|PGJIT_DEFORM\|PGJIT_INLINE\|PGJIT_OPT3" \
       source/src/backend/ | head -20

# Lifecycle:
grep -n "llvm_create_context\|llvm_release_context\|llvm_mutable_module\|llvm_get_function" \
       source/src/backend/jit/llvm/llvmjit.c

# EXPLAIN integration:
grep -rn "InstrJitAgg\|JIT:\|jit_instrument" \
       source/src/backend/commands/explain.c
```

## Cross-references

- [[jit-expression-codegen]] — IR generation from `EEOP_*` ops in `llvmjit_expr.c`.
- [[jit-tuple-deform-and-inline]] — specialized deform + cross-module inlining.
- [[aggregate-hash-vs-sort]] — `ExecBuildAggTrans` builds the mega-expression that JIT targets.
- [[expression-evaluator-flow]] — `EEOP_*` ops that JIT translates.
- `source/src/backend/jit/README` — design overview.
