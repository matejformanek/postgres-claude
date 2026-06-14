# FmgrInfo — cached function metadata for fmgr calls

`FmgrInfo` is the catalog-lookup-once-call-many-times cache
for SQL-callable C functions. Doing the catalog lookup (oid →
proname, prolang, proowner, prosrc, etc.) per row would
dominate executor cost. `FmgrInfo` does it once, stores the
resolved function pointer and metadata, and the executor
loops on cheap calls afterward.

Anchors:
- `source/src/include/fmgr.h:56-67` — the struct
  [verified-by-code]
- `source/src/include/fmgr.h:85-96` — companion
  `FunctionCallInfoBaseData`
- `source/src/backend/utils/fmgr/fmgr.c` — implementation
- `.claude/skills/fmgr-and-spi/SKILL.md` — companion skill

## The struct

```c
typedef struct FmgrInfo
{
    PGFunction      fn_addr;       /* function or handler pointer */
    Oid             fn_oid;        /* OID of function (NOT handler) */
    short           fn_nargs;      /* # input args (0..FUNC_MAX_ARGS) */
    bool            fn_strict;     /* "strict" (NULL in → NULL out) */
    bool            fn_retset;     /* returns a set */
    unsigned char   fn_stats;      /* collect stats if track_functions > this */
    void           *fn_extra;      /* function-private cache */
    MemoryContext   fn_mcxt;       /* memory context for fn_extra */
    Node           *fn_expr;       /* expression parse tree for call, or NULL */
} FmgrInfo;
```

[verified-by-code `fmgr.h:56-67`]

The 9 fields, grouped by purpose:

- **Resolution result**: `fn_addr`, `fn_oid`.
- **Calling convention**: `fn_nargs`, `fn_strict`, `fn_retset`.
- **Observability**: `fn_stats` (gated against
  `track_functions`).
- **Per-function private cache**: `fn_extra` + `fn_mcxt`.
- **Parse-time context**: `fn_expr`.

## fn_extra — the function's scratch cache

The most subtle field. `fn_extra` is a **void pointer the
called function may use for any purpose**. Typical use:

```c
Datum
my_func(PG_FUNCTION_ARGS)
{
    if (fcinfo->flinfo->fn_extra == NULL)
    {
        MemoryContext old = MemoryContextSwitchTo(
                              fcinfo->flinfo->fn_mcxt);
        fcinfo->flinfo->fn_extra = my_setup();
        MemoryContextSwitchTo(old);
    }
    MyCache *cache = fcinfo->flinfo->fn_extra;
    /* use cache for the call */
}
```

Critical: allocations for `fn_extra` MUST happen in `fn_mcxt`,
NOT in `CurrentMemoryContext`. The caller's context likely has
a much shorter lifetime than the FmgrInfo (which lives until
the planner / executor releases the cache).

Set-returning functions, regex functions, and parse-once
functions like `jsonb_path_*` all use `fn_extra` for compiled
state.

## The lookup entry points

```c
extern void fmgr_info(Oid functionId, FmgrInfo *finfo);
extern void fmgr_info_cxt(Oid functionId, FmgrInfo *finfo,
                          MemoryContext mcxt);
```

[verified-by-code `fmgr.h:124-132`]

- `fmgr_info(oid, finfo)` — fills the FmgrInfo using
  `CurrentMemoryContext` as `fn_mcxt`.
- `fmgr_info_cxt(oid, finfo, ctx)` — caller specifies the
  context. Use when the FmgrInfo will outlive
  `CurrentMemoryContext`.

After either call, `finfo` is ready for `FunctionCallInvoke`
calls.

## The companion FunctionCallInfoBaseData

```c
typedef struct FunctionCallInfoBaseData
{
    FmgrInfo       *flinfo;          /* ptr to cached lookup */
    Node           *context;         /* call context */
    Node           *resultinfo;
    Oid             fncollation;
    bool            isnull;          /* function must set if NULL */
    short           nargs;
    NullableDatum   args[FLEXIBLE_ARRAY_MEMBER];
} FunctionCallInfoBaseData;
```

[verified-by-code `fmgr.h:85-96`]

Carries the per-call arguments + result-isnull flag. The
flexible array at the tail means `sizeof(FunctionCallInfoBaseData)`
is wrong for sizing; use `SizeForFunctionCallInfo(nargs)`
[verified-by-code `fmgr.h:102-104`].

## Stack vs heap allocation

[verified-by-code `fmgr.h:110-118`]

```c
LOCAL_FCINFO(fcinfo, 2);     /* 2-arg fcinfo on the stack */
fcinfo->args[0].value = ...;
```

The `LOCAL_FCINFO` macro is the canonical on-stack allocation
— it uses a union to guarantee alignment and reserves the
right amount of space for `nargs` arguments.

For dynamic sizes:

```c
FunctionCallInfo fcinfo = palloc(SizeForFunctionCallInfo(nargs));
```

Allocating a bare `FunctionCallInfoBaseData` is **wrong** —
the flexible-array space isn't reserved. The struct's typedef
name (`*BaseData`, not `*Data`) is deliberately chosen to
break pre-v12 code that did this
[from-comment `fmgr.h:81-83`].

## The strictness gate

`fn_strict = true` means: if any argument is NULL, the function
is **not called** — the result is NULL automatically. The
fmgr layer checks this; the function body sees only non-NULL
args.

For functions that need to distinguish "argument was NULL" vs
"argument was non-NULL but produced NULL output," set
`fn_strict = false` (the catalog's `prosrc` reflects this).
The function then must call `PG_ARGISNULL(n)` per argument.

## fn_expr — the parse tree

When called from an SQL expression context (an `FuncExpr`),
the fmgr layer passes the parsed expression as `fn_expr`. This
lets functions inspect their own call context — e.g.
`get_fn_expr_argtype(flinfo, 0)` returns the resolved type of
the first argument including polymorphism (`anyelement`,
`anyarray`).

For directly-invoked functions (e.g. `OidFunctionCall1`),
`fn_expr` is NULL.

## Common review-time concerns

- **Always `pfree` per-call allocations.** `fn_extra` is the
  exception — it lives in `fn_mcxt` and survives across calls.
- **Switch to `fn_mcxt` for `fn_extra` allocation.**
  Forgetting this means `fn_extra` ends up in the per-tuple
  expr context and is freed mid-execution.
- **Use `PG_GETARG_*_PP`** for varlena args (preserve packed
  short header). `_P` forces a long-header detoast, which is
  more expensive for short strings.
- **`SizeForFunctionCallInfo(nargs)` not `sizeof(fcinfo)`.**
  The flexible array makes the struct's static size wrong.
- **`LOCAL_FCINFO(name, nargs)` for the stack case** — uses a
  union for alignment. Hand-rolled `char buf[...]` won't
  guarantee alignment.

## Invariants

- **[INV-1]** `fn_extra` allocations live in `fn_mcxt`, NOT
  the caller's context.
- **[INV-2]** `fn_strict` is the fmgr-layer NULL gate; strict
  functions never see NULL args.
- **[INV-3]** `FunctionCallInfoBaseData` has flexible-array
  tail; use `SizeForFunctionCallInfo(nargs)`.
- **[INV-4]** `fmgr_info`'s output is good until the
  context (`fn_mcxt`) is reset.
- **[INV-5]** `fn_expr` is only set for SQL-expression
  callers, not direct invocations.

## Useful greps

- All `fmgr_info` sites:
  `grep -RIn 'fmgr_info\|fmgr_info_cxt' source/src/backend | wc -l`
- `fn_extra` use patterns:
  `grep -RIn 'fn_extra' source/src/backend/utils/adt | head -20`
- LOCAL_FCINFO callers:
  `grep -RIn 'LOCAL_FCINFO' source/src/backend | head -20`

## Cross-references

- `.claude/skills/fmgr-and-spi/SKILL.md` — the skill covering
  the fmgr API including `PG_GETARG_*`, `PG_RETURN_*`,
  argument macros.
- `.claude/skills/memory-contexts/SKILL.md` — `fn_mcxt` is
  one of the context-lifetime decisions.
- `.claude/skills/extension-development/SKILL.md` —
  PG_FUNCTION_INFO_V1 / fmgr_info call chain.
- `knowledge/data-structures/tupletableslot.md` — slot ops
  are accessed via fmgr-style vtables (different mechanism,
  similar pattern).
- `source/src/include/fmgr.h` — public API + struct
  definitions.
- `source/src/backend/utils/fmgr/fmgr.c` — implementation;
  fmgr_info resolution + stat tracking.
