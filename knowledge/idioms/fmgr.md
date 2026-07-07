# fmgr — the PostgreSQL function manager

Long-form notes on how SQL-level function invocation actually crosses
into C code. Operational quick-reference lives in
`.claude/skills/fmgr-and-spi/SKILL.md`; this doc covers the "why".

All confidence tags `[verified-by-code]` unless otherwise noted, against
`source/` at the repository's pinned commit.

---

## 1. What the fmgr is for

Every SQL-callable function (builtins, language handlers, extensions,
PL/pgSQL bodies, operator implementations, index support, …) is invoked
through a single uniform C signature:

```c
typedef Datum (*PGFunction) (FunctionCallInfo fcinfo);
```

[verified-by-code] `src/include/fmgr.h:40`. Every callee, regardless of
language, ultimately has this signature — even PLs do, with the
language's call handler standing in as `fn_addr` and dispatching
internally [from-readme] `src/backend/utils/fmgr/README:36-44`.

The point of having one signature is to make function lookup
independent of function call: the executor does the (expensive)
`pg_proc` lookup once per query and then calls the cached `FmgrInfo`
many times per row [from-readme] lines 14-19.

## 2. The two structs

### `FmgrInfo` — the per-function lookup cache

```c
typedef struct FmgrInfo
{
    PGFunction    fn_addr;        /* C entry point or handler */
    Oid           fn_oid;
    short         fn_nargs;
    bool          fn_strict;
    bool          fn_retset;
    unsigned char fn_stats;
    void         *fn_extra;       /* callee-private cache */
    MemoryContext fn_mcxt;        /* lifetime of fn_extra */
    Node         *fn_expr;        /* parse-time call expr (or NULL) */
} FmgrInfo;
```

[verified-by-code] `src/include/fmgr.h:56-67`.

`fn_oid` is filled in **last** by `fmgr_info_cxt_security`, and only
once the rest is valid — other code may observe a partially-built
FmgrInfo and uses `fn_oid != InvalidOid` as the "fully initialized"
test [verified-by-code] `src/backend/utils/fmgr/fmgr.c:158-178`.

`fn_extra` is the callee's per-query scratchpad. Allocate any cache
attached to it in `fn_mcxt`, not `CurrentMemoryContext`, because the
caller's current context can be a per-tuple short-lived one
[from-readme] lines 432-439.

`fn_expr` is parse-time information about the call (the `FuncExpr`
node, in normal cases). It's how polymorphic functions resolve
`anyelement` → concrete type via `get_fn_expr_argtype` /
`get_fn_expr_rettype` [verified-by-code]
`src/include/fmgr.h:774-775`. `DirectFunctionCall*` does not set up an
FmgrInfo at all, so polymorphic resolution is impossible there.

### `FunctionCallInfoBaseData` — the per-call struct

```c
typedef struct FunctionCallInfoBaseData
{
    FmgrInfo       *flinfo;
    Node           *context;
    Node           *resultinfo;
    Oid             fncollation;
    bool            isnull;
    short           nargs;
    NullableDatum   args[FLEXIBLE_ARRAY_MEMBER];
} FunctionCallInfoBaseData;
```

[verified-by-code] `src/include/fmgr.h:85-96`.

It is a flexible-array-member struct: you cannot stack-allocate a bare
`FunctionCallInfoBaseData` because it has zero space for args. The
struct was renamed from `FunctionCallInfoData` in v12 precisely to
break pre-v12 callers that did `FunctionCallInfoData fcinfo;` on the
stack [from-comment] `src/include/fmgr.h:80-83`.

The supported allocations are:

- **Stack:** `LOCAL_FCINFO(fcinfo, NARGS)` — a union trick that
  reserves enough char[] under a `FunctionCallInfoBaseData`-aligned
  member [verified-by-code] `src/include/fmgr.h:110-118`.
- **Heap:** `palloc(SizeForFunctionCallInfo(nargs))`
  [verified-by-code] `src/include/fmgr.h:102-104`.

`context` and `resultinfo` are open-ended slots for extensions of the
call protocol. Documented uses [from-readme] lines 235-276:

- Trigger functions: `context` = `TriggerData *`
- Aggregate transition/final: `context` = `AggState *` or `WindowAggState *`
- Window functions: `context` = `WindowObject *`
- Procedures (CALL): `context` = `CallContext *` (carries `atomic` flag)
- Input functions handling soft errors: `context` = `ErrorSaveContext *`
- Set-returning functions: `resultinfo` = `ReturnSetInfo *`

A callee MUST always `IsA()`-check before assuming a particular context
type — fmgr itself does not constrain what's pointed at.

## 3. The version-1 calling convention

[verified-by-code] `src/include/fmgr.h:382-394`: "Version-0 ('old
style') is not supported anymore". The README's leading note also
confirms V0 was removed [from-readme] lines 6-8.

V1 is the convention you see in every modern function: take a single
`FunctionCallInfo fcinfo`, fetch args via `PG_GETARG_*`, return a
`Datum` (or `PG_RETURN_NULL()` setting `fcinfo->isnull`).

The `PG_FUNCTION_INFO_V1(funcname)` macro emits a sibling function
`pg_finfo_<funcname>` that returns a `Pg_finfo_record { .api_version =
1 }`. The dynamic loader calls this via `dlsym` to confirm ABI
compatibility before calling the function itself [verified-by-code]
`src/include/fmgr.h:417-426`. Builtin (compiled-in) functions skip
this — they're known to be V1 by construction
[from-comment] `src/include/fmgr.h:390-392`.

`PG_MODULE_MAGIC` (or `PG_MODULE_MAGIC_EXT`) emits a similar `dlsym`
target carrying:

- PG major version
- `FUNC_MAX_ARGS`
- `INDEX_MAX_KEYS`
- `NAMEDATALEN`
- `FLOAT8PASSBYVAL` (vestigial — always true on supported platforms)
- `FMGR_ABI_EXTRA` (a `pg_config_manual.h`-controlled string)

[verified-by-code] `src/include/fmgr.h:468-498`. Mismatch on any of
these gets you the famous `incompatible_module_error()`.

## 4. How fmgr resolves SQL → C

When the executor needs to call a SQL function with `pg_proc` OID
`functionId`, it does:

```c
FmgrInfo flinfo;
fmgr_info(functionId, &flinfo);
/* fcinfo built around &flinfo, args filled in ... */
Datum result = FunctionCallInvoke(fcinfo);    /* = (*fcinfo->flinfo->fn_addr)(fcinfo) */
```

`fmgr_info` → `fmgr_info_cxt_security` does
[verified-by-code] `src/backend/utils/fmgr/fmgr.c:128-216`:

1. **Builtin fast path.** If `functionId <= fmgr_last_builtin_oid` and
   the OID indexes into `fmgr_builtins[]`, copy `nargs`/`strict`/
   `retset`/`func` from there and return. No syscache hit.
   [verified-by-code] lines 168-180.
2. **pg_proc lookup.** SearchSysCache1(PROCOID, ...). Copy `pronargs`,
   `proisstrict`, `proretset`.
3. **Security-definer wrap.** If `prosecdef`, non-null `proconfig`, or
   a plugin registered `needs_fmgr_hook`, the resolved `fn_addr`
   becomes `fmgr_security_definer` instead of the real function. The
   real OID is stashed so that handler can re-resolve internally.
   [from-comment] lines 192-201.
4. **Language dispatch.** For language `C`: `fmgr_info_C_lang` does
   `dlsym` of `funcname` and its `pg_finfo_funcname`, asserts api_version
   == 1, caches the lookup in `CFuncHash`. For other languages:
   `fmgr_info_other_lang` looks up the language's call handler in
   `pg_language` and sets `fn_addr` to the handler.

After this, `fn_addr` is either:

- the C function (builtin / extension C),
- `fmgr_security_definer` (recursive wrapping),
- a PL call handler (PL/pgSQL, PL/Python, …),
- `fmgr_sql` for SQL-language functions.

## 5. The caller-side entry points

Three families in `src/backend/utils/fmgr/fmgr.c`:

| Family | Signature | When to use |
|---|---|---|
| `DirectFunctionCallN[Coll]` | `(PGFunction, [coll,] args...)` | You know the C function pointer, can't be NULL in or out, no flinfo. [verified-by-code] lines 794-1056 |
| `FunctionCallN[Coll]` | `(FmgrInfo*, [coll,] args...)` | You've already done `fmgr_info`. Reuses flinfo. [verified-by-code] lines 1114-1395 |
| `OidFunctionCallN[Coll]` | `(Oid, [coll,] args...)` | Convenience: `fmgr_info` + `FunctionCallN` each call. Discards flinfo every time. [verified-by-code] lines 1402-1517 |

Specialized I/O wrappers: `InputFunctionCall`, `OutputFunctionCall`,
`ReceiveFunctionCall`, `SendFunctionCall`, plus `Safe` variants that
honor an `ErrorSaveContext` [verified-by-code]
`src/backend/utils/fmgr/fmgr.c:1531-1700+`,
`src/include/fmgr.h:746-766`.

The `Coll`-less wrappers are macros that pass `InvalidOid` for
collation [verified-by-code] `src/include/fmgr.h:687-743`. New code
that handles collation-sensitive types should use the `Coll` form.

Important: every `DirectFunctionCallN` and `OidFunctionCallN` elogs
ERROR if the callee sets `fcinfo->isnull = true`. They are NOT
NULL-tolerant. To call a function that may return NULL, build the
fcinfo yourself with `LOCAL_FCINFO` and `FunctionCallInvoke`
[verified-by-code] e.g. lines 807-809.

## 6. Strictness — short-circuit at the executor

A function with `proisstrict = true` does NOT receive a call when any
input is NULL; the executor returns NULL directly. So strict callees
need not handle `PG_ARGISNULL` [from-readme] lines 107-112.

Non-strict callees MUST check `PG_ARGISNULL(n)` before any
`PG_GETARG_*(n)` — the Datum value at a NULL argument is unspecified
[from-readme] lines 99-101.

## 7. Soft errors and ErrorSaveContext

Standard `ereport(ERROR)` longjmps out to a (sub)transaction abort.
For input-function-style validation that's overkill — PG 16 added a
"soft error" path: caller passes an `ErrorSaveContext` in
`fcinfo->context`, callee uses `errsave(fcinfo->context, ...)` or
`ereturn(fcinfo->context, dummy, ...)` which fills the context node
and returns normally [from-readme] lines 279-340.

If `fcinfo->context` is NULL or some other Node, both behave exactly
like `ereport(ERROR)` — so a function that's been adapted to soft
errors still works as a regular hard-error function for older callers.

The contract: a soft error MUST be safe to recover from without
transaction cleanup. Out-of-memory, internal corruption, lock
acquisition failure, etc. must still be hard errors.

## 8. Set-returning functions

[from-readme] lines 343-417 and [verified-by-code]
`src/include/funcapi.h:240-336`.

A function with `proretset = true` is called with
`fcinfo->resultinfo = ReturnSetInfo *`. It picks one of two modes:

### Value-Per-Call

The function is invoked once per result row plus one final "done"
call. Per-call state lives in `FuncCallContext *` allocated in
`multi_call_memory_ctx` and reached via
`fcinfo->flinfo->fn_extra`. `SRF_IS_FIRSTCALL()` literally tests
`fn_extra == NULL` [verified-by-code] `src/include/funcapi.h:305`,
which is why an SRF cannot use `fn_extra` for its own cache.

The executor may stop calling before exhaustion (LIMIT, OFFSET, error)
— SRFs MUST NOT count on running to completion for resource cleanup.
File descriptors held across calls are a known anti-pattern
[from-comment] `src/include/funcapi.h:279-289`.

### Materialize

The function builds the entire result into a `Tuplestore` in one call
and stashes it on `rsinfo->setResult` + `rsinfo->setDesc` + sets
`rsinfo->returnMode = SFRM_Materialize`. The tuplestore and tupledesc
MUST live in `rsinfo->econtext->ecxt_per_query_memory`, NOT in
`CurrentMemoryContext` [verified-by-code]
`src/backend/utils/fmgr/funcapi.c:75-122` (`InitMaterializedSRF`).

The function's Datum return value is ignored in materialize mode
(convention: `PG_RETURN_NULL()`). [from-readme] lines 393-400.

Helper: `InitMaterializedSRF(fcinfo, flags)` does the sanity checks
(rsinfo non-NULL, allowedModes includes Materialize) and the
tuplestore/tupdesc setup [verified-by-code]
`src/backend/utils/fmgr/funcapi.c:75-123`.

## 9. Polymorphic types

Functions declared with `anyelement`, `anyarray`, `anyrange`,
`anymultirange`, `anycompatible*`, etc. need runtime type resolution.
The fmgr leaves this to the callee via:

- `get_fn_expr_argtype(flinfo, n)` — concrete Oid of arg n
- `get_fn_expr_rettype(flinfo)` — concrete Oid of return type
- `get_call_result_type(fcinfo, &typeId, &tupdesc)` — for composite
  returns, possibly involving RECORD resolution from `expectedDesc`
  [verified-by-code] `src/backend/utils/fmgr/funcapi.c:276-285`.

All of these need `flinfo->fn_expr` set, which it is for SQL-driven
calls but not for `DirectFunctionCall*`. So polymorphic functions are
not safely callable via `DirectFunctionCall*`.

## 10. Error handling inside an fmgr function

- Use `ereport(ERROR, ...)` for hard errors. The current
  (sub)transaction aborts. See the error-handling skill for SQLSTATE
  conventions.
- Use `errsave(fcinfo->context, ...)` or `ereturn(...)` for soft
  errors IF and only if `fcinfo->context` may legitimately be an
  `ErrorSaveContext` (input functions, currently).
- Never `setjmp` / `longjmp` directly. PG_TRY/PG_CATCH is the only
  blessed mechanism, and even then prefer to let ereport unwind.

If you must `PG_TRY` around code that may ereport (because you need
to do something on failure other than aborting the txn), remember to
`CopyErrorData` + `FlushErrorState` and you'll usually want
`BeginInternalSubTransaction` to genuinely roll back partial state.
See the SPI subxact pattern in `knowledge/idioms/spi.md`.

## 11. fn_extra — query-lifetime cache slot

`FmgrInfo.fn_extra` is reserved by the fmgr protocol for the callee.
It is NULL when first filled and is preserved across repeated calls
through the same FmgrInfo. Idiomatic usage:

```c
typedef struct { /* whatever cache */ } MyState;

Datum my_func(PG_FUNCTION_ARGS)
{
    MyState *st = fcinfo->flinfo->fn_extra;
    if (st == NULL)
    {
        MemoryContext old = MemoryContextSwitchTo(fcinfo->flinfo->fn_mcxt);
        st = palloc0(sizeof(*st));
        /* ... initialize ... */
        fcinfo->flinfo->fn_extra = st;
        MemoryContextSwitchTo(old);
    }
    /* ... use st ... */
}
```

[from-readme] lines 432-439, [verified-by-code]
`src/include/fmgr.h:64-65`.

Caveats:

- Callers are not *required* to reuse FmgrInfo, so `fn_extra` is a hint
  only — code must work when it's NULL on every call.
- SRF value-per-call mode uses `fn_extra` itself; you can't share.
- Memory MUST come from `fn_mcxt`. The most common bug is using
  `CurrentMemoryContext`, which (in expressions, SRFs, aggregates) is
  a per-tuple context that disappears between rows.

## 12. Hooks

Two hookable points [verified-by-code] `src/include/fmgr.h:831-855`:

- `needs_fmgr_hook(fn_oid)` — predicate, asked at `fmgr_info` time
- `fmgr_hook(event, flinfo, &private)` — called at FHET_START / FHET_END /
  FHET_ABORT around each invocation

Used by loadable security policy modules. If the hook returns true,
`fn_addr` becomes `fmgr_security_definer` to give the hook a place to
trap entry/exit.

## 13. Cross-references

- Operational quick-reference: `.claude/skills/fmgr-and-spi/SKILL.md`
- SPI side: `knowledge/idioms/spi.md`
- Memory contexts: `knowledge/idioms/memory-contexts.md`
- Error reporting: `knowledge/idioms/error-handling.md`
- Manual: <https://www.postgresql.org/docs/current/xfunc-c.html> [from-docs]

## Call sites
<!-- callsites:auto -->

*Auto-extracted via glossary cross-reference of backticked C identifiers in this doc.*
*Refresh via `scripts/populate-idiom-callsites-v2.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`contrib/amcheck/verify_heapam`](../files/contrib/amcheck/verify_heapam.md) | — | `InitMaterializedSRF` — Sets up a set-returning function in materialize mode: it builds the result `Tuplestore` and tuple descriptor and... |
| [`contrib/intarray/_int_op`](../files/contrib/intarray/_int_op.md) | — | `PG_MODULE_MAGIC_EXT` — The extended form of `PG_MODULE_MAGIC` (PG 18) that additionally embeds the extension's name and version into the... |
| [`contrib/postgres_fdw/postgres_fdw.c`](../files/contrib/postgres_fdw/postgres_fdw.c.md) | — | `InputFunctionCall` — The fmgr wrapper that invokes a type's text-input function (cstring → Datum), handling the three-argument convention |
| [`src/backend/access/common/scankey.c`](../files/src/backend/access/common/scankey.c.md) | — | `fmgr_info` — Fills an `FmgrInfo` lookup cache for a function OID — resolving the C entry point, argument count, and strictness — s |
| [`src/backend/catalog/pg_proc.c`](../files/src/backend/catalog/pg_proc.c.md) | — | `pg_proc` — The system catalog with one row per function, procedure, and aggregate (the latter pairs with `pg_aggregate`), holdin |
| [`src/backend/parser/parse_expr.c`](../files/src/backend/parser/parse_expr.c.md) | — | `FuncExpr` — The `primnodes |
| [`src/backend/utils/adt/misc.c`](../files/src/backend/utils/adt/misc.c.md) | — | `PG_ARGISNULL` — Macro a SQL-callable C function uses to test whether argument N was passed SQL NULL before touching it; mandatory for |
| [`src/backend/utils/error/elog.c`](../files/src/backend/utils/error/elog.c.md) | — | `FlushErrorState` — The elog |
| [`src/include/fmgr.h`](../files/src/include/fmgr.h.md) | — | `FUNC_MAX_ARGS` — The hard cap on the number of arguments a function may take, defined as 100 in `pg_config_manual |
| [`src/include/pg_config_manual.h`](../files/src/include/pg_config_manual.h.md) | — | `INDEX_MAX_KEYS` — A compile-time constant (default 32, set in `pg_config_manual |
| [`src/pl/plpython/plpy_exec`](../files/src/pl/plpython/plpy_exec.md) | — | `multi_call_memory_ctx` — The longer-lived memory context a set-returning function uses across its value-per-call invocations (set up via... |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md)
- [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md)
- [`add-new-cast`](../scenarios/add-new-cast.md)
- [`add-new-data-type`](../scenarios/add-new-data-type.md)
- [`add-new-error-code`](../scenarios/add-new-error-code.md)
- [`add-new-extension`](../scenarios/add-new-extension.md)
- [`add-new-operator`](../scenarios/add-new-operator.md)
- [`add-new-operator-class`](../scenarios/add-new-operator-class.md)
- [`add-new-pg-stat-view`](../scenarios/add-new-pg-stat-view.md)
- [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md)
- [`add-new-system-view`](../scenarios/add-new-system-view.md)
- [`add-new-table-am`](../scenarios/add-new-table-am.md)

<!-- /scenarios:auto -->
