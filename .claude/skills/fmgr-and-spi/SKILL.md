---
name: fmgr-and-spi
description: PostgreSQL fmgr (function manager) and SPI (Server Programming Interface) calling conventions — how to write a SQL-callable C function (PG_FUNCTION_INFO_V1, PG_GETARG_*, PG_RETURN_*, PG_ARGISNULL, SRF_* and Materialize mode, composite/polymorphic types) and how to run SQL from inside one (SPI_connect → SPI_execute → SPI_finish, plan caching, cursors, the subxact / aborted-subxact rule, common return codes). Use whenever editing or adding C code that defines a `Datum foo(PG_FUNCTION_ARGS)` entry point, calls another fmgr function (`OidFunctionCall*`, `DirectFunctionCall*`, `FunctionCall*Coll`), or runs SQL queries via `SPI_*` from a backend extension, trigger, or PL handler.
---

# fmgr and SPI — operational playbook

The fmgr is how every SQL-callable C function in PostgreSQL gets invoked.
SPI is how that same C code runs SQL back into the executor. They sit
adjacent in any non-trivial extension or PL.

All confidence tags are `[verified-by-code]` unless noted.

---

## 1. Writing a SQL-callable C function (fmgr V1)

V0 ("old style") was removed; V1 is the only supported convention.
[verified-by-code] `src/include/fmgr.h:382-394` ("Version-0 ... is not supported anymore. Version 1 is the call convention defined in this header file").

### 1.1 Minimum boilerplate

```c
#include "postgres.h"
#include "fmgr.h"

PG_MODULE_MAGIC;                              /* exactly once per .so */

PG_FUNCTION_INFO_V1(my_func);                 /* once per exported func */

Datum
my_func(PG_FUNCTION_ARGS)
{
    int32   a = PG_GETARG_INT32(0);
    text   *t = PG_GETARG_TEXT_PP(1);

    /* ... */
    PG_RETURN_INT32(a + VARSIZE_ANY_EXHDR(t));
}
```

`PG_FUNCTION_ARGS` expands to `FunctionCallInfo fcinfo`
[verified-by-code] `src/include/fmgr.h:193`.

`PG_FUNCTION_INFO_V1(name)` defines `pg_finfo_<name>()` returning
`{ api_version = 1 }`, marks the function `PGDLLEXPORT`, and (importantly)
emits an extern declaration of the C function so you don't have to
[verified-by-code] `src/include/fmgr.h:417-426`.

`PG_MODULE_MAGIC` (or `PG_MODULE_MAGIC_EXT(.name=..., .version=...)`)
must appear exactly once in a multi-source-file module
[verified-by-code] `src/include/fmgr.h:441-549`.

### 1.2 Argument extraction

| Macro | Returns | Use for |
|---|---|---|
| `PG_GETARG_INT32(n)` / `_INT64` / `_FLOAT8` / `_BOOL` / `_OID` | scalar | pass-by-value types |
| `PG_GETARG_TEXT_PP(n)` / `_BYTEA_PP` / `_VARCHAR_PP` | `text *` etc, packed | preferred for varlena read-only |
| `PG_GETARG_TEXT_P_COPY(n)` | modifiable palloc'd copy | when you'll mutate it |
| `PG_GETARG_RAW_VARLENA_P(n)` | still-toasted | rare; you handle detoast |
| `PG_GETARG_DATUM(n)` | raw `Datum` | passing through |
| `PG_GETARG_POINTER(n)` | `void *` | opaque/internal types |
| `PG_GETARG_CSTRING(n)` | `char *` | type input functions |
| `PG_GETARG_HEAPTUPLEHEADER(n)` | composite | row-typed inputs |
| `PG_NARGS()` | int | variadic / generic |
| `PG_GET_COLLATION()` | Oid | collation-sensitive funcs |

`_PP` variants are preferred over the older `_P` variants — they may
return packed (1-byte header) datums, so use `VARSIZE_ANY_EXHDR()` /
`VARDATA_ANY()` to inspect them
[verified-by-code] `src/include/fmgr.h:285-339` and README lines 202-227.

### 1.3 NULL handling

A function marked `STRICT` in `pg_proc` will not be called when any
argument is NULL; the executor short-circuits and returns NULL itself.
[from-readme] `src/backend/utils/fmgr/README:107-112`.

If the function is **not** strict you MUST check before extracting:

```c
if (PG_ARGISNULL(0))
    PG_RETURN_NULL();
int32 a = PG_GETARG_INT32(0);
```

`PG_ARGISNULL(n)` is just `fcinfo->args[n].isnull`
[verified-by-code] `src/include/fmgr.h:209`.

`PG_RETURN_NULL()` sets `fcinfo->isnull = true` and returns `(Datum) 0`
[verified-by-code] `src/include/fmgr.h:346-347`.

### 1.4 Returning values

```c
PG_RETURN_INT32(42);
PG_RETURN_TEXT_P(cstring_to_text("hello"));
PG_RETURN_NULL();
PG_RETURN_VOID();          /* C-level void; NOT the same as SQL NULL */
PG_RETURN_DATUM(d);
```

For varlena results: palloc the output in `CurrentMemoryContext` and
return it untoasted — the tuple toaster decides whether to compress
[from-readme] lines 230-233.

### 1.5 Detoast hygiene for index opclass / btree / hash support functions

Functions registered in `pg_amop` / `pg_amproc` MUST avoid leaking
detoasted copies, because executor cleanup of expression memory is
deferred. Use `PG_FREE_IF_COPY(ptr, n)` before returning
[from-readme] lines 217-227, [verified-by-code] `src/include/fmgr.h:260-264`.

### 1.6 Soft errors (input functions and friends)

If `fcinfo->context` is an `ErrorSaveContext` node, use
`errsave(fcinfo->context, ...)` or `ereturn(fcinfo->context, dummy, ...)`
instead of `ereport(ERROR, ...)`. With a non-ErrorSaveContext context
both fall through to ereport(ERROR) [from-readme] lines 279-340. This
matters for `_in` input functions added in PG 16.

### 1.7 Composite arg / row construction

```c
HeapTupleHeader t = PG_GETARG_HEAPTUPLEHEADER(0);
Oid             tupType  = HeapTupleHeaderGetTypeId(t);
int32           tupTypmod= HeapTupleHeaderGetTypMod(t);
TupleDesc       tupdesc  = lookup_rowtype_tupdesc(tupType, tupTypmod);
HeapTupleData   tup;
tup.t_len = HeapTupleHeaderGetDatumLength(t);
ItemPointerSetInvalid(&tup.t_self);
tup.t_tableOid = InvalidOid;
tup.t_data = t;
/* deform with heap_deform_tuple, read attrs ... */
ReleaseTupleDesc(tupdesc);          /* MUST pair with lookup */
```

`ReleaseTupleDesc` is mandatory after `lookup_rowtype_tupdesc`
[inferred] from common-pattern usage across `contrib/`.

To return a composite: build with `heap_form_tuple(tupdesc, values, nulls)`
then `PG_RETURN_DATUM(HeapTupleGetDatum(tup))`. If the tupdesc came from
RECORD (transient), call `BlessTupleDesc(tupdesc)` first so a typmod is
assigned [verified-by-code] `src/backend/utils/fmgr/funcapi.c:112-114`.

### 1.8 Polymorphic functions

For `anyelement` / `anyarray` / `anyrange` / `anymultirange`,
resolve the actual type at runtime via:

```c
Oid argtype = get_fn_expr_argtype(fcinfo->flinfo, 0);
Oid rettype = get_fn_expr_rettype(fcinfo->flinfo);
```

[verified-by-code] `src/include/fmgr.h:774-775`. Both need
`fcinfo->flinfo->fn_expr` to be set, which it is for normal SQL
invocations but not for `DirectFunctionCallN` (no flinfo).

### 1.9 Set-returning functions — Value-Per-Call mode

```c
PG_FUNCTION_INFO_V1(my_srf);
Datum
my_srf(PG_FUNCTION_ARGS)
{
    FuncCallContext *funcctx;
    MyState         *state;

    if (SRF_IS_FIRSTCALL())
    {
        MemoryContext oldctx;
        funcctx = SRF_FIRSTCALL_INIT();
        oldctx  = MemoryContextSwitchTo(funcctx->multi_call_memory_ctx);
        state   = palloc0(sizeof(*state));
        /* compute max_calls, open files, build TupleDesc ... */
        funcctx->max_calls = state->n;
        funcctx->user_fctx = state;
        MemoryContextSwitchTo(oldctx);
    }
    funcctx = SRF_PERCALL_SETUP();
    state   = funcctx->user_fctx;

    if (funcctx->call_cntr < funcctx->max_calls)
    {
        Datum r = /* ... build one row ... */;
        SRF_RETURN_NEXT(funcctx, r);
    }
    SRF_RETURN_DONE(funcctx);
}
```

Boilerplate template in [verified-by-code] `src/include/funcapi.h:242-289`,
macros in lines 305-336.

`SRF_IS_FIRSTCALL()` tests `fcinfo->flinfo->fn_extra == NULL` —
`fn_extra` is therefore reserved by the SRF machinery and you cannot
co-opt it [verified-by-code] `src/include/funcapi.h:305`.

Value-per-call SRFs may be aborted by LIMIT etc and must NOT hold
non-memory resources (file descriptors, locks) across calls
[from-comment] `src/include/funcapi.h:279-289`.

### 1.10 Set-returning functions — Materialize mode

For SRFs that need to do work in one shot (file I/O, single query
walk) or that can't be cleanly chunked. Use the helper:

```c
PG_FUNCTION_INFO_V1(my_mat_srf);
Datum
my_mat_srf(PG_FUNCTION_ARGS)
{
    ReturnSetInfo *rsinfo = (ReturnSetInfo *) fcinfo->resultinfo;
    Datum    values[NCOLS];
    bool     nulls[NCOLS];

    InitMaterializedSRF(fcinfo, 0);   /* fills rsinfo->setResult & setDesc */

    /* for each row: */
    tuplestore_putvalues(rsinfo->setResult, rsinfo->setDesc, values, nulls);

    PG_RETURN_NULL();                 /* materialize ignores return value */
}
```

`InitMaterializedSRF` allocates the tuplestore in
`rsinfo->econtext->ecxt_per_query_memory` — NOT in `CurrentMemoryContext`
[verified-by-code] `src/backend/utils/fmgr/funcapi.c:100-122`. This is
the single most common SRF pitfall.

Flag `MAT_SRF_USE_EXPECTED_DESC` reuses the caller's `expectedDesc`;
`MAT_SRF_BLESS` calls `BlessTupleDesc` to assign a typmod for RECORD
[verified-by-code] `src/include/funcapi.h:296-298`.

### 1.11 Calling another fmgr function from C

Three flavors, in increasing setup cost:

```c
/* (a) one-shot, no flinfo, no NULLs allowed */
Datum d = DirectFunctionCall2(textcat,
                              CStringGetTextDatum("foo"),
                              CStringGetTextDatum("bar"));
```

`DirectFunctionCall*Coll` builds a stack `LOCAL_FCINFO`, fills args,
invokes, elogs ERROR if the callee returned NULL
[verified-by-code] `src/backend/utils/fmgr/fmgr.c:794-811`. Callee must
not depend on `fcinfo->flinfo` because there isn't one.

```c
/* (b) repeated calls of a function looked up by OID */
FmgrInfo flinfo;
fmgr_info(my_oid, &flinfo);                   /* once per query */
for (...)
    FunctionCall1Coll(&flinfo, InvalidOid, arg);
```

```c
/* (c) one-shot from OID */
OidFunctionCall1(my_oid, arg);                /* = fmgr_info + FunctionCall1 */
```

[verified-by-code] `src/backend/utils/fmgr/fmgr.c:1403-1410`. (c) is
convenient but throws away the FmgrInfo every call — never use it in
a hot loop.

For datatype I/O specifically:

```c
Datum d = OidInputFunctionCall(typinput, "42", typioparam, typmod);
char *s = OidOutputFunctionCall(typoutput, d);
```

[verified-by-code] `src/backend/utils/fmgr/fmgr.c:1531-1566` and
`src/include/fmgr.h:746-766`.

### 1.12 fn_extra — per-call cache slot

`FmgrInfo.fn_extra` is reserved for the callee to stash query-lifetime
cache (e.g. a parsed FmgrInfo for a sub-function, a compiled regex,
etc.). It must be allocated in `flinfo->fn_mcxt`, NOT
`CurrentMemoryContext` (the latter is typically a per-tuple short-lived
context) [from-readme] lines 432-439, [verified-by-code]
`src/include/fmgr.h:64-65`.

```c
if (fcinfo->flinfo->fn_extra == NULL)
{
    MemoryContext oldctx = MemoryContextSwitchTo(fcinfo->flinfo->fn_mcxt);
    fcinfo->flinfo->fn_extra = palloc0(sizeof(MyCache));
    /* ... populate cache ... */
    MemoryContextSwitchTo(oldctx);
}
MyCache *c = fcinfo->flinfo->fn_extra;
```

### 1.13 Three things easy to get wrong about fmgr

1. **Materialize SRF in CurrentMemoryContext.** Tuplestore + TupleDesc
   MUST live in `rsinfo->econtext->ecxt_per_query_memory`. Otherwise
   they vanish before the caller reads them. The helper handles this;
   hand-rolling does not.
2. **PG_FREE_IF_COPY in opclass support functions.** Toast leakage in
   functions called from index searches accumulates until end of
   transaction. Strict btree/hash/gist support functions must pfree
   detoasted copies.
3. **fn_extra allocated in CurrentMemoryContext.** If the caller is a
   per-tuple ExprContext (common in expressions and SRFs), the cache
   gets freed between rows and you re-pay the lookup. Always switch to
   `fn_mcxt`.

---

## 2. SPI — running SQL from inside a backend

### 2.1 The lifecycle

```c
int ret = SPI_connect();
if (ret != SPI_OK_CONNECT)
    elog(ERROR, "SPI_connect failed: %s", SPI_result_code_string(ret));

ret = SPI_execute("SELECT count(*) FROM t WHERE x > $1", true /*read_only*/, 0);
if (ret != SPI_OK_SELECT)
    elog(ERROR, "SPI_execute failed: %s", SPI_result_code_string(ret));

/* SPI_processed is the row count; SPI_tuptable holds the results */
for (uint64 i = 0; i < SPI_processed; i++)
{
    HeapTuple t = SPI_tuptable->vals[i];
    char *v = SPI_getvalue(t, SPI_tuptable->tupdesc, 1);
    /* ... */
}

SPI_finish();
```

`SPI_connect` pushes a stack entry, creates the "SPI Proc" and
"SPI Exec" memory contexts, switches `CurrentMemoryContext` to "SPI Proc",
and resets the global `SPI_processed`, `SPI_tuptable`, `SPI_result`
[verified-by-code] `src/backend/executor/spi.c:101-180`.

`SPI_finish` switches back to the caller's context, deletes both
contexts (which auto-frees tuptables), and pops the stack
[verified-by-code] `src/backend/executor/spi.c:182-216`.

### 2.2 Return-code protocol

`SPI_execute` and friends return one of:

- positive `SPI_OK_*` on success: `SELECT`, `INSERT`, `UPDATE`,
  `DELETE`, `INSERT_RETURNING`, `UTILITY`, `MERGE`, etc.
  [verified-by-code] `src/include/executor/spi.h:82-100`.
- negative `SPI_ERROR_*` on bad arguments etc — these are NOT thrown
  as errors, they're returned. Real query errors are still ereported.

Always check the return code and use `SPI_result_code_string(ret)` for
log messages [verified-by-code] `src/backend/executor/spi.c:1973-2045`.

Globals after a successful execute:
- `SPI_processed` (uint64) — number of rows processed/returned
- `SPI_tuptable` — for SELECT-like commands; NULL for UTILITY etc

### 2.3 Plan caching

Avoid re-parsing in loops:

```c
Oid   argtypes[1] = { INT4OID };
SPIPlanPtr plan = SPI_prepare("SELECT * FROM t WHERE id = $1", 1, argtypes);
if (plan == NULL)
    elog(ERROR, "SPI_prepare: %s", SPI_result_code_string(SPI_result));

/* Optional: keep the plan beyond SPI_finish */
SPI_keepplan(plan);   /* reparents to CacheMemoryContext */

for (int i = 0; i < n; i++)
{
    Datum vals[1] = { Int32GetDatum(ids[i]) };
    int ret = SPI_execute_plan(plan, vals, NULL, true, 0);
    /* ... consume SPI_tuptable ... */
}

SPI_freeplan(plan);   /* only call after the last execute */
```

`SPI_prepare` returns NULL on error; the code is in the global
`SPI_result` (because the return type is a pointer)
[verified-by-code] `src/backend/executor/spi.c:861-901`.

`SPI_keepplan` is one-way; reparents the plan's memory context under
`CacheMemoryContext` and pins underlying `CachedPlanSource`s
[verified-by-code] `src/backend/executor/spi.c:977-1001`.

### 2.4 Cursor pattern

Use this for large result sets to avoid materializing in memory:

```c
SPIPlanPtr plan = SPI_prepare("SELECT id FROM huge", 0, NULL);
Portal p = SPI_cursor_open(NULL, plan, NULL, NULL, true);
for (;;)
{
    SPI_cursor_fetch(p, true /*forward*/, 1000);
    if (SPI_processed == 0)
        break;
    for (uint64 i = 0; i < SPI_processed; i++) { /* ... */ }
}
SPI_cursor_close(p);
SPI_freeplan(plan);
```

[verified-by-code] `src/backend/executor/spi.c:1446-1464, 1807-1875`.

### 2.5 Returning values across SPI_finish

`SPI_finish` deletes the SPI Proc context — anything palloc'd inside
the SPI session vanishes. To return data to the caller, allocate it in
the caller's context with `SPI_palloc` / `SPI_copytuple` /
`SPI_returntuple` — these switch to `_SPI_current->savedcxt` (the
caller's context at SPI_connect time)
[verified-by-code] `src/backend/executor/spi.c:1048-1104, 1339-1378`.

```c
SPI_connect();
SPI_execute("SELECT name FROM t WHERE id=1", true, 1);
char *name = SPI_getvalue(SPI_tuptable->vals[0], SPI_tuptable->tupdesc, 1);
char *copy = MemoryContextStrdup(_SPI_current->savedcxt, name);  /* or SPI_palloc */
SPI_finish();
/* `copy` is now usable; `name` is gone */
```

### 2.6 Atomic vs non-atomic, COMMIT/ROLLBACK inside SPI

By default `SPI_connect()` is atomic — the caller cannot run COMMIT or
ROLLBACK [verified-by-code] `src/backend/executor/spi.c:142-143`.

Use `SPI_connect_ext(SPI_OPT_NONATOMIC)` from a CALL'd procedure to
allow transaction control. `SPI_commit` / `SPI_rollback` then work,
but only if no subtransaction is open
[verified-by-code] `src/backend/executor/spi.c:239-257`.

### 2.7 Subxact pattern (PL/pgSQL EXCEPTION blocks)

Wrap a fault-recoverable SPI call in a subtransaction:

```c
MemoryContext oldctx = CurrentMemoryContext;
ResourceOwner oldowner = CurrentResourceOwner;
BeginInternalSubTransaction(NULL);
PG_TRY();
{
    SPI_execute("...maybe-fails...", false, 0);
    ReleaseCurrentSubTransaction();
}
PG_CATCH();
{
    MemoryContextSwitchTo(oldctx);
    ErrorData *edata = CopyErrorData();
    FlushErrorState();
    RollbackAndReleaseCurrentSubTransaction();
    /* SPI state from inside the subxact is cleaned up automatically
       by AtEOSubXact_SPI */
    /* handle edata ... */
}
PG_END_TRY();
CurrentResourceOwner = oldowner;
```

`AtEOSubXact_SPI` pops any SPI stack entries whose `connectSubid`
matches the dying subxact and resets executor state and tuptables
created within it [verified-by-code]
`src/backend/executor/spi.c:482-572`.

**The aborted-subxact rule:** once a subxact has aborted, do NOT
attempt further SPI work in the same SPI stack frame until you have
unwound to the SPI_connect() level that owns it. SPI work *inside* an
aborted (sub)transaction is not supported — the executor state is
gone. [inferred] from the AtEOSubXact_SPI cleanup; see also the
`internal_xact` flag at lines 263-317.

### 2.8 Three things easy to get wrong about SPI

1. **Returning palloc'd data past SPI_finish.** Anything not allocated
   via `SPI_palloc`/`SPI_copytuple` in the caller's context gets freed
   when SPI_finish deletes the SPI Proc context. Copy or move before
   finishing.
2. **Forgetting `SPI_keepplan`.** A bare `SPI_prepare` puts the plan in
   the SPI Proc context, so it disappears at SPI_finish. If the plan
   needs to outlive a single connect/finish pair (e.g. cached on
   `fn_extra`), call `SPI_keepplan` while still inside SPI.
3. **Using `SPI_execute` inside a strict aborted subxact.** SPI is
   not for use after a subxact has aborted; you must unwind first.
   Calls before BeginInternalSubTransaction's frame end are fine.

---

## 3. Grep cheat-sheet

```bash
# Find every C function exported to SQL:
grep -rn 'PG_FUNCTION_INFO_V1' source/contrib/

# Find SRF examples by mode:
grep -rln 'SRF_FIRSTCALL_INIT'   source/   # value-per-call
grep -rln 'InitMaterializedSRF'  source/   # materialize

# Find SPI usage patterns:
grep -rln 'SPI_connect'          source/contrib/ source/src/pl/
grep -rln 'SPI_execute_plan'     source/contrib/

# Look up an unfamiliar SPI_OK_* code:
grep -n 'SPI_OK_\|SPI_ERROR_'    source/src/include/executor/spi.h
```

## 4. Cross-references

- Long-form details: `knowledge/idioms/fmgr.md`, `knowledge/idioms/spi.md`.
- Memory-context rules referenced throughout: `knowledge/idioms/memory-contexts.md`.
- Error/soft-error reporting: `.claude/skills/error-handling/SKILL.md`.
- Official chapters: <https://www.postgresql.org/docs/current/xfunc-c.html>,
  <https://www.postgresql.org/docs/current/spi.html>.
