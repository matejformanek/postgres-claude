# `src/include/funcapi.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~360
- **Source:** `source/src/include/funcapi.h`

The set-returning-function (SRF) and composite-return infrastructure
sitting on top of `fmgr.h`. Defines `FuncCallContext` (per-SRF cached
state across multiple calls), `AttInMetadata` (per-column input
function info), and the SRF_* macro family. Also covers the
ValuePerCall and Materialize modes, the VARIADIC-argument extraction
helper, and the polymorphic-argtype resolver. [verified-by-code]

## API / declarations

### Composite-type construction

- `AttInMetadata { TupleDesc tupdesc; FmgrInfo *attinfuncs; Oid
  *attioparams; int32 *atttypmods; }` (`funcapi.h:35-48`) — caches
  per-attribute input function FmgrInfo + I/O param OID + typmod so
  `BuildTupleFromCStrings` doesn't redo lookups each call.
- `BlessTupleDesc(tupdesc)` (`funcapi.h:224`) — "blesses" an
  anonymous tupdesc so it can be used to return labeled tuples.
  Required before `heap_form_tuple` use.
- `TupleDescGetAttInMetadata(tupdesc)` (`funcapi.h:225`) — builds
  AttInMetadata; also Blesses internally.
- `BuildTupleFromCStrings(attinmeta, char **values)` (`funcapi.h:226`)
  — composes a HeapTuple from C strings.
- `HeapTupleHeaderGetDatum(tuple)` (`funcapi.h:227`),
  `HeapTupleGetDatum(tuple)` static inline (`funcapi.h:229-233`).
- Obsolete: `TupleGetDatum(slot, tuple)` macro
  (`funcapi.h:236`), `RelationNameGetTupleDesc(relname)`,
  `TypeGetTupleDesc(typeoid, colaliases)` (`funcapi.h:220-221`).

### Return-type resolution (`funcapi.h:146-185`)

- `TypeFuncClass { TYPEFUNC_SCALAR, TYPEFUNC_COMPOSITE,
  TYPEFUNC_COMPOSITE_DOMAIN, TYPEFUNC_RECORD, TYPEFUNC_OTHER }`.
- `get_call_result_type(fcinfo, &resultTypeId, &resultTupleDesc)` —
  derives result type from FunctionCallInfo (uses caller's
  expression context).
- `get_expr_result_type(expr, &..., &...)` — same but from an
  expression node.
- `get_func_result_type(funcOid, &..., &...)` — only the function OID
  (caveat: "Do *not* use this if you can use one of the others",
  `funcapi.h:135-137`).
- `get_expr_result_tupdesc(expr, noError)` — wrapper.
- `resolve_polymorphic_argtypes(numargs, argtypes, argmodes,
  call_expr)` — fills in `anyelement`/`anyarray`/`anycompatible`
  based on the call expression's actual argument types.
- `get_func_arg_info(procTup, &argtypes, &argnames, &argmodes)` —
  reads pg_proc tuple.
- `get_func_input_arg_names`, `get_func_trftypes`,
  `get_func_result_name`,
  `build_function_result_tupdesc_d(prokind, proallargtypes,
  proargmodes, proargnames)`,
  `build_function_result_tupdesc_t(procTuple)`.

### SRF support — ValuePerCall mode (`funcapi.h:239-336`)

- `FuncCallContext { uint64 call_cntr; uint64 max_calls; void
  *user_fctx; AttInMetadata *attinmeta; MemoryContext
  multi_call_memory_ctx; TupleDesc tuple_desc; }`
  (`funcapi.h:57-114`) — the per-SRF state struct, stored in
  `fcinfo->flinfo->fn_extra` between calls.
- `init_MultiFuncCall(fcinfo)` (`funcapi.h:301`), `per_MultiFuncCall`,
  `end_MultiFuncCall`.
- `SRF_IS_FIRSTCALL()` = `(fcinfo->flinfo->fn_extra == NULL)`.
- `SRF_FIRSTCALL_INIT()` = `init_MultiFuncCall(fcinfo)`.
- `SRF_PERCALL_SETUP()` = `per_MultiFuncCall(fcinfo)`.
- `SRF_RETURN_NEXT(_funcctx, _result)` (`funcapi.h:311-318`) — bumps
  call_cntr, sets `rsi->isDone = ExprMultipleResult`, returns Datum.
- `SRF_RETURN_NEXT_NULL(_funcctx)` (`funcapi.h:320-327`) — same but
  returns NULL.
- `SRF_RETURN_DONE(_funcctx)` (`funcapi.h:329-336`) — calls
  `end_MultiFuncCall`, sets `rsi->isDone = ExprEndResult`, returns
  NULL.

### SRF — Materialize mode

- `InitMaterializedSRF(fcinfo, flags)` (`funcapi.h:299`) — sets up a
  tuplestore-backed SRF. Flags:
  - `MAT_SRF_USE_EXPECTED_DESC = 0x01` — use expectedDesc as tupdesc.
  - `MAT_SRF_BLESS = 0x02` — `BlessTupleDesc` it.

### VARIADIC argument extraction

- `extract_variadic_args(fcinfo, variadic_start, convert_unknown,
  &values, &types, &nulls)` (`funcapi.h:356`) — returns # of
  elements stored, or -1 for `VARIADIC NULL`.

## Notable invariants / details

- The `FuncCallContext` lives in `multi_call_memory_ctx`, which is
  the lifetime of the executor node (typically per-query). Allocs
  done during `SRF_IS_FIRSTCALL()` must be in this context to
  survive across calls (`funcapi.h:94-101`). [from-comment]
- "There is no guarantee that a SRF using ValuePerCall mode will be
  run to completion; for example, a query with LIMIT might stop
  short of fetching all the rows" (`funcapi.h:279-281`). Therefore
  ValuePerCall SRFs MUST NOT hold non-memory resources (file
  descriptors, locks) between calls. Use Materialize mode or
  RegisterExprContextCallback for those. [from-comment]
- `BlessTupleDesc` is required for any tupdesc that flows through
  `heap_form_tuple` and out to a client. `TupleDescGetAttInMetadata`
  does it for you (`funcapi.h:192-196`).
- "the tupledesc should be copied if it is to be accessed over a
  long period" (`funcapi.h:127-128`) — `get_call_result_type` may
  return a TupleDesc tied to a cache entry that gets invalidated.
- The composite/record distinction matters: `TYPEFUNC_RECORD` means
  the rowtype is determined by the OUT parameters or call-site
  AS-clause, not the function's declared return type. Resolving it
  needs the call expression (`funcapi.h:122-141`).
- `polymorphic_argtypes` resolution requires the call expression —
  cannot be done from OID alone. This is why `get_func_result_type`
  is the inferior API. [from-comment]
- `multi_call_memory_ctx` is the SRF's per-tuplestore context, and
  Materialize mode SRFs return tuples through `rsi->setResult`, not
  through `SRF_RETURN_*`. Mixing modes silently breaks: the SRF
  macros set `rsi->isDone`, but Materialize mode requires
  `rsi->isDone = ExprEndResult` set by caller.

## Potential issues

- `funcapi.h:279-288` — the "no resource cleanup before
  SRF_RETURN_DONE" rule is comment-only. An SRF that opens a file
  descriptor in FIRSTCALL_INIT and closes it in RETURN_DONE will
  leak fd if LIMIT cuts the scan short. No header-level Assert.
  [ISSUE-undocumented-invariant: SRF non-memory resource leakage
  on early-exit is comment-only (likely)]
- `funcapi.h:305` — `SRF_IS_FIRSTCALL` tests `fn_extra == NULL`. An
  SRF that uses `fn_extra` for non-SRF caching (legitimate per
  fmgr.h convention) will mis-detect first-call. [ISSUE-api-shape:
  SRF_IS_FIRSTCALL conflates `fn_extra` usage (likely)]
- `funcapi.h:311-318` — `SRF_RETURN_NEXT` macro reads
  `fcinfo->resultinfo` without checking if it's actually a
  `ReturnSetInfo`. Callers that call an SRF via DirectFunctionCall
  (no rsi) crash. [ISSUE-correctness: SRF_RETURN_NEXT assumes
  resultinfo is ReturnSetInfo (likely)]
- `funcapi.h:296-298` — flag bits `MAT_SRF_USE_EXPECTED_DESC` /
  `MAT_SRF_BLESS` are bare uint32 — easy to swap. [ISSUE-style:
  flag bits should be enum (nit)]
- `funcapi.h:230-233` — `HeapTupleGetDatum` static inline reads
  `tuple->t_data` with no NULL check. SRFs that accidentally pass
  a tuple-from-pg_class with null `t_data` crash. [ISSUE-correctness:
  HeapTupleGetDatum has no NULL-`t_data` guard (nit)]
- `funcapi.h:356-358` — `extract_variadic_args` `convert_unknown` is
  bool — silently changes call semantics. [ISSUE-style: bare bool
  api parameter (nit)]
