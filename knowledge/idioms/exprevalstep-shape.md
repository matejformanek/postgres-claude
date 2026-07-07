# ExprEvalStep shape — the 64-byte cap and the out-of-line state pattern

`ExprEvalStep` is the union-tagged step type that drives `ExecInterpExpr`
— a tight switch-dispatch interpreter that walks a flat array of steps.
The struct is hard-capped by `StaticAssertDecl(sizeof(ExprEvalStep) <=
64, ...)` so each step is one cache line on x86_64 / aarch64. Any new
opcode whose per-step state needs more than ~4 fields (or any array, or
any nested `ExprState`) must put its state out-of-line and store ONLY a
pointer in the `d` union. Getting this wrong is a compile-time failure
on the StaticAssertDecl, not a subtle runtime regression — but it's
easy to design yourself into the trap before you see the assert fire.

The cap exists for one reason: every expression in the system runs
through `ExecInterpExpr` (or its JIT mirror), iterating over an
`ExprEvalStep *steps` array. If `sizeof(ExprEvalStep) > 64` the loop
straddles cache lines on every step and the whole system slows. The
comment at the top of the union says so explicitly:

> "The union should be kept to no more than 40 bytes on 64-bit systems
> (so that the entire struct is no more than 64 bytes, a single
> cacheline on common systems)."
> [from-comment `source/src/include/executor/execExpr.h:313-317`]

Anchors:
- `source/src/include/executor/execExpr.h:300-307` — `ExprEvalStep`
  outer struct (opcode + resvalue + resnull + `d` union)
  [verified-by-code]
- `source/src/include/executor/execExpr.h:780-781` — the
  `StaticAssertDecl` itself [verified-by-code]
- `source/src/include/executor/execExpr.h:565-580` — the two `sbsref*`
  d-union entries, each carrying only `struct SubscriptingRefState
  *state` (the canonical out-of-line pattern) [verified-by-code]
- `source/src/include/executor/execExpr.h:785-812` — the
  `SubscriptingRefState` struct itself (lives in the SAME header as
  `ExprEvalStep`, immediately after the assert) [verified-by-code]
- `source/src/include/executor/execExpr.h:334-342` — `d.var`, the
  canonical small inline payload (3 fields, fits trivially)
  [verified-by-code]

## The struct, the comment, and the cap

[verified-by-code `source/src/include/executor/execExpr.h:300-317, 780-781`]:

```c
typedef struct ExprEvalStep
{
    intptr_t    opcode;         /* dispatch tag (or computed-goto pointer) */
    Datum      *resvalue;       /* where to store the result */
    bool       *resnull;

    /*
     * Inline data for the operation.  Inline data is faster to access, but
     * also bloats the size of all instructions.  The union should be kept to
     * no more than 40 bytes on 64-bit systems (so that the entire struct is
     * no more than 64 bytes, a single cacheline on common systems).
     */
    union { ... } d;            /* one struct per opcode family */
} ExprEvalStep;

StaticAssertDecl(sizeof(ExprEvalStep) <= 64,
                 "size of ExprEvalStep exceeds 64 bytes");
```

Outer overhead: `opcode` (8) + `resvalue` (8) + `resnull` (8) = 24
bytes, leaving 40 bytes for the union. The union's size is the MAX of
all members, so every entry competes for that same 40-byte budget —
adding one fat entry penalizes every other opcode's steps too.

## Inline vs out-of-line, side-by-side

Tiny inline payload — `d.var` is 3 fields, no allocation
[verified-by-code `source/src/include/executor/execExpr.h:334-342`]:

```c
/* for EEOP_INNER/OUTER/SCAN/OLD/NEW_[SYS]VAR */
struct
{
    int                 attnum;
    Oid                 vartype;
    VarReturningType    varreturningtype;
}           var;
```

Out-of-line payload — `d.sbsref_subscript` and `d.sbsref` keep only a
single pointer in the union, with the real state in a separately-
allocated `SubscriptingRefState`
[verified-by-code `source/src/include/executor/execExpr.h:565-580`]:

```c
/* for EEOP_SBSREF_SUBSCRIPTS */
struct
{
    ExecEvalBoolSubroutine subscriptfunc;
    /* too big to have inline */
    struct SubscriptingRefState *state;
    int         jumpdone;
}           sbsref_subscript;

/* for EEOP_SBSREF_OLD / ASSIGN / FETCH */
struct
{
    ExecEvalSubroutine subscriptfunc;
    /* too big to have inline */
    struct SubscriptingRefState *state;
}           sbsref;
```

Note the `/* too big to have inline */` comment: this is the in-tree
convention. Note also that BOTH `sbsref*` entries point at the same
`SubscriptingRefState` — the first step initializes it, subsequent
steps read and update it. Out-of-line state can be shared across
steps because only the pointer is copied.

The state struct lives right after the `StaticAssertDecl`, by
convention [verified-by-code `source/src/include/executor/execExpr.h:784-812`]:

```c
/* Non-inline data for container operations */
typedef struct SubscriptingRefState
{
    bool        isassignment;
    void       *workspace;
    int         numupper;
    bool       *upperprovided;
    Datum      *upperindex;
    bool       *upperindexnull;
    int         numlower;
    bool       *lowerprovided;
    Datum      *lowerindex;
    bool       *lowerindexnull;
    Datum       replacevalue;
    bool        replacenull;
    Datum       prevvalue;
    bool        prevnull;
} SubscriptingRefState;
```

This struct is ~120 bytes. Inline, it would balloon every
`ExprEvalStep` in the system to ~144 bytes regardless of opcode (the
union sizes to its max member). Out-of-lining it costs one extra
pointer-deref per execution but preserves the cache-line property for
every OTHER opcode.

Other out-of-line examples in the same union, naming the convention:

- `d.window_func.wfstate` → `WindowFuncExprState *`
- `d.subplan.sstate` → `SubPlanState *`
- `d.jsonexpr.jsestate` → `struct JsonExprState *`
- `d.json_constructor.jcstate` → `struct JsonConstructorExprState *`

Pattern: a `<Opcode>State` typedef beside the union, one pointer field
in the d-union (`state`, `wfstate`, `sstate`, `jcstate`, `jsestate`).

## The failure mode (F22 incident)

Sesvars Phase 8 added inline write-through-indirection — `SELECT
@arr[i] := v` and `@arr[lo:hi] := v`. The natural first design was to
add subscript bookkeeping directly to `d.sesvar_write` (`is_slice`,
`lower_provided`, two `Datum *` slots, two `bool *` slots). The union
grew to ~80 bytes; the build failed at compile time:

```
error: static assertion failed: "size of ExprEvalStep exceeds 64 bytes"
```

The fix mirrors `SubscriptingRefState` verbatim
[verified-by-code `postgresql-dev-feature-sesvars/src/include/executor/execExpr.h:441-457, 825-833`]:

```c
/* for EEOP_SESVAR_WRITE */
struct
{
    char       *name;
    Oid         vartype;
    int16       typlen;
    bool        typbyval;
    Oid         varcollid;
    /*
     * NULL for plain "@x := v"; non-NULL when the assignment is
     * "@arr[i] := v" or "@arr[lo:hi] := v".  Out-of-lined into a
     * separate allocation because ExprEvalStep is hard-capped at 64
     * bytes.
     */
    struct SesVarIndirectionState *indir;
}           sesvar_write;

/* ... after the StaticAssertDecl ... */

typedef struct SesVarIndirectionState
{
    bool        is_slice;
    bool        lower_provided;
    Datum      *upper_idx;
    bool       *upper_null;
    Datum      *lower_idx;
    bool       *lower_null;
} SesVarIndirectionState;
```

The `indir` pointer is NULL for the common case (`@x := v`, no
subscript) and non-NULL only for the indirection path. Every step
still fits in 64 bytes.

## Lifetime + ownership

Out-of-line state is `palloc`'d during expression compilation
(`ExecInitExpr` → `ExecInitExprRec`), in whatever MemoryContext is
active at that time. For executor-resident ExprStates that's typically
`estate->es_query_cxt` — `ExecPrepareExpr` switches to it explicitly
[verified-by-code `source/src/backend/executor/execExpr.c:770-776`]:

```c
oldcontext = MemoryContextSwitchTo(estate->es_query_cxt);
result = ExecInitExpr(node, NULL);
MemoryContextSwitchTo(oldcontext);
```

The state has the same lifetime as the surrounding `ExprState` — freed
when the per-query context resets. Sesvars' `SesVarIndirectionState`
follows this pattern
[verified-by-code `postgresql-dev-feature-sesvars/src/backend/executor/execExpr.c:1154-1177`]:

```c
SesVarIndirectionState *istate;

istate = (SesVarIndirectionState *) palloc0(sizeof(SesVarIndirectionState));
istate->is_slice = ai->is_slice;
istate->upper_idx = (Datum *) palloc0(sizeof(Datum));
...
scratch.d.sesvar_write.indir = istate;
```

Don't: allocate in `TopMemoryContext` (leaks across statements), or
per-step at execution time (would need explicit `pfree` and breaks the
"steps array is read-only at runtime" assumption).

## Decision rubric

| Per-opcode state shape | Choice |
|---|---|
| ≤ 4 scalar fields, total ≤ ~24 bytes, no arrays, no nested ExprStates | inline in `d.<opcode>` |
| > 4 fields, OR any array, OR any nested `ExprState *`, OR any pointer that itself owns allocations | out-of-line via `<Opcode>State *` |
| Borderline / unsure | out-of-line (always safe; inline can break the assert) |

Indicators that out-of-line is the right call: any `Datum *` / `bool *`
array, any `ExprState *` field (recursive compilation produces nested
ExprStates with their own steps arrays), any large workspace
(XML / JSON / conversion maps).

## Inline vs out-of-line — comparison

| Aspect | Inline `d.<opcode>` | Out-of-line `<Opcode>State *` |
|---|---|---|
| Where state lives | In the `ExprEvalStep` itself | Separate palloc'd struct |
| Budget | Shares 40 bytes with every other opcode's union member | Unbounded; only one pointer (8 bytes) in the union |
| Allocation | Free (the steps array itself) | One `palloc` at `ExecInitExpr` time |
| Cache behavior | Optimal — state in same cache line as opcode | One extra deref per step |
| Compile-time safety | Can break the 64-byte assert if grown | Always under budget |
| Lifetime | Tied to the steps array | Tied to the owning ExprState's MemoryContext |
| Shared across steps | No — each step gets its own copy | Yes — multiple steps can point at the same state |
| Canonical examples | `d.var`, `d.fetch`, `d.aggref` | `d.sbsref*`, `d.window_func`, `d.subplan`, `d.jsonexpr` |
| Cost of being wrong | Build fails with explicit assert error | None — just one extra deref |

## Origin

Sesvars F22, 2026-06-22 retro. Follow-up #2 (`7197b54c1d0` on branch
`feature_sesvars` in `postgresql-dev-feature-sesvars/`) introduced
`SesVarIndirectionState` as the out-of-line carrier for write-through-
indirection state on `EEOP_SESVAR_WRITE`. The initial Phase 8 design
tried to inline the subscript bookkeeping inside `d.sesvar_write` and
tripped the `StaticAssertDecl` at compile time. Out-of-lining via a
separate state struct (pattern verbatim from `SubscriptingRefState`)
brought the union back under budget.

Full retro: `sessions/2026-06-22-sesvars-v3-retro.md` §F22.



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/execExpr.c`](../files/src/backend/executor/execExpr.c.md) | 770 | [verified-by-code -776] |
| [`src/backend/executor/execExpr.c`](../files/src/backend/executor/execExpr.c.md) | — | ExecInitExprRec, fills the steps array |
| [`src/backend/executor/execExprInterp.c`](../files/src/backend/executor/execExprInterp.c.md) | — | ExecInterpExpr, the dispatch loop that reads op->d.<opcode> |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 300 | ExprEvalStep outer struct (opcode + resvalue + resnull + d union) |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 313 | > [from-comment -317] |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 334 | d.var, the canonical small inline payload (3 fields, fits trivially) |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 565 | the two sbsref d-union entries, each carrying only struct SubscriptingRefState state (the canonical... |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 780 | the StaticAssertDecl itself |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 784 | convention [verified-by-code -812] |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | 785 | the SubscriptingRefState struct itself (lives in the SAME header as ExprEvalStep, immediately after the... |
| [`src/include/executor/execExpr.h`](../files/src/include/executor/execExpr.h.md) | — | ExprEvalStep, the assert, SubscriptingRefState, every d-union member |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/expression-evaluator-flow.md` — surrounding
  `ExecInitExpr` / `ExecInterpExpr` machinery
- `knowledge/idioms/node-types.md` — Expr-node walker obligations that
  produce the EEOP steps in the first place
- `knowledge/idioms/jit-expression-codegen.md` — JIT mirror reads the
  same `ExprEvalStep` shape
- `source/src/include/executor/execExpr.h` — `ExprEvalStep`, the
  assert, `SubscriptingRefState`, every d-union member
- `source/src/backend/executor/execExpr.c` — `ExecInitExprRec`,
  fills the steps array
- `source/src/backend/executor/execExprInterp.c` — `ExecInterpExpr`,
  the dispatch loop that reads `op->d.<opcode>`

## Open questions / unverified

- Whether the 64-byte cap is relaxed on 32-bit platforms (pointers
  are 4 bytes, effective budget wider) [unverified] — no evidence of
  conditional asserts; the rule appears uniform.
- Whether `jit/llvm/llvmjit_expr.c` independently asserts the
  `ExprEvalStep` size [unverified] — JIT reads the C struct directly,
  so the C-side assert is presumably sufficient, but I haven't traced
  the LLVM IR path.
