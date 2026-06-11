# `src/backend/utils/fmgr/fmgr.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~2166
- **Source:** `source/src/backend/utils/fmgr/fmgr.c`

The function manager — the dispatch layer translating a `pg_proc` OID
into a C function pointer plus calling-convention metadata, and
providing the actual call helpers (`OidFunctionCallN`,
`FunctionCallN`, `DirectFunctionCallN`, `InputFunctionCall`, etc.).
Also implements the `fmgr_security_definer` trampoline that handles
SECURITY DEFINER, `proconfig` GUC overrides, and the `fmgr_hook`
plugin point. The file is the canonical entry from SQL into any C or
PL function. [verified-by-code]

## API surface (grouped)

### Lookup

- `fmgr_info(functionId, finfo)` — populate `FmgrInfo` in
  `CurrentMemoryContext`. [verified-by-code]
- `fmgr_info_cxt(functionId, finfo, mcxt)` — same with explicit
  memory context for subsidiary allocations (PL fn caches etc.).
  Use this when storing FmgrInfo long-term. [verified-by-code]
- `fmgr_info_copy(dst, src, destcxt)` — bitcopy + zero `fn_extra`
  (subsidiary info is lost; will be recomputed lazily).
  [verified-by-code] [from-comment]
- `fmgr_symbol(functionId, *mod, *fn)` — reverse map: return the
  module + function name implementing this OID (for JIT,
  introspection). [verified-by-code]
- `fmgr_internal_function(proname)` — look up an internal builtin
  by name; returns OID or InvalidOid. Used by `fmgr_internal_validator`.
  [verified-by-code]
- Static: `fmgr_isbuiltin(id)`, `fmgr_lookupByName(name)`,
  `fmgr_info_C_lang`, `fmgr_info_other_lang`, `lookup_C_func`,
  `record_C_func`. [verified-by-code]
- `fetch_finfo_record(filehandle, funcname)` — load
  `pg_finfo_<name>` from the dlopen handle to discover
  `Pg_finfo_record { api_version }`. Only api_version 1 is supported.
  [verified-by-code]

### Direct call (no FmgrInfo, no setup cost — for builtins called
from C)

- `DirectFunctionCall1Coll` through `DirectFunctionCall9Coll` —
  immediate `(*func)(fcinfo)` with `LOCAL_FCINFO` on the stack.
  Errors if the callee returns NULL. [verified-by-code]
- `CallerFInfoFunctionCall1` / `CallerFInfoFunctionCall2` — like
  `DirectFunctionCallN` but pass a caller-supplied `FmgrInfo` so the
  callee can use `fn_extra` / `fn_mcxt`. Comment warns these fields
  describe the caller, not the callee, so the contract is delicate.
  [verified-by-code] [from-comment]

### Looked-up call

- `FunctionCall0Coll` through `FunctionCall9Coll` — uses
  `FunctionCallInvoke` (which is `flinfo->fn_addr(fcinfo)`).
  [verified-by-code]
- `OidFunctionCall0Coll` through `OidFunctionCall9Coll` —
  `fmgr_info` + `FunctionCallNColl`. Each call does a fresh lookup;
  the comment warns to cache via `fmgr_info` for repeated calls.
  [verified-by-code] [from-comment]

### I/O function helpers

- `InputFunctionCall(flinfo, str, typioparam, typmod)` — calls a
  `_in` function with 3 args. `str == NULL` + strict ⇒ returns 0
  without invocation. [verified-by-code]
- `InputFunctionCallSafe(flinfo, str, typioparam, typmod, escontext,
  *result)` — soft-error variant. If `escontext` is an
  `ErrorSaveContext`, a parse failure inside the input function fills
  the context and returns false; otherwise behaves like
  `InputFunctionCall`. [verified-by-code] [from-comment]
- `DirectInputFunctionCallSafe(func, str, …, escontext, *result)` —
  given a direct C function pointer (no FmgrInfo). Assumes strict.
  [verified-by-code]
- `OutputFunctionCall(flinfo, val)` — `_out` invocation; returns
  `char *`. Do not call on NULL. [verified-by-code]
- `ReceiveFunctionCall(flinfo, buf, typioparam, typmod)` — `_recv`,
  with NULL-buf handling parallel to InputFunctionCall. [verified-by-code]
- `SendFunctionCall(flinfo, val)` — `_send`; result is forced
  non-toasted. [verified-by-code] [from-comment]
- `OidInputFunctionCall` / `OidOutputFunctionCall` /
  `OidReceiveFunctionCall` / `OidSendFunctionCall` — convenience
  wrappers; comment notes "only to be used in seldom-executed code
  paths. They are not only slow but leak memory." [verified-by-code]
  [from-comment]

### Toast helpers (here for historical reasons)

- `pg_detoast_datum(datum)` / `pg_detoast_datum_copy(datum)` /
  `pg_detoast_datum_slice(datum, first, count)` /
  `pg_detoast_datum_packed(datum)` — wrappers around
  `detoast_attr*` from `access/detoast`. The `_packed` variant
  leaves compressed-but-inline datums alone. [verified-by-code]

### fn_expr introspection (for polymorphic functions)

- `get_fn_expr_rettype(flinfo)` — returns result type via `exprType`
  on the cached call expression. [verified-by-code]
- `get_fn_expr_argtype(flinfo, argnum)` / `get_call_expr_argtype(expr,
  argnum)` — type of the Nth argument. Walks `FuncExpr` / `OpExpr` /
  `DistinctExpr` / `ScalarArrayOpExpr` / `NullIfExpr` / `WindowFunc`
  arglist. Special-case: `ScalarArrayOpExpr` arg 1 is the array
  element type. [verified-by-code]
- `get_fn_expr_arg_stable(flinfo, n)` / `get_call_expr_arg_stable(expr,
  n)` — true if arg is `Const` or extern `Param`. [verified-by-code]
- `get_fn_expr_variadic(flinfo)` — was the call written with
  VARIADIC? Only meaningful for VARIADIC ANY. [verified-by-code]

### Opclass-options (reuse `fn_expr` as a bytea Const)

- `set_fn_opclass_options(flinfo, options)` — store `bytea *` (or
  NULL) as a synthetic `Const(BYTEAOID)` in `fn_expr`. [verified-by-code]
- `has_fn_opclass_options(flinfo)` — true if fn_expr is a non-null
  bytea Const. [verified-by-code]
- `get_fn_opclass_options(flinfo)` — return the bytea; ERROR if not
  present. [verified-by-code]

### Validator helper

- `CheckFunctionValidatorAccess(validatorOid, functionOid)` —
  verifies the validator matches the function's language and the
  caller has USAGE on the language + EXECUTE on the function.
  Pivotal security gate: prevents calling an untrusted-language
  validator on an attacker-supplied function body. The block
  comment (line 2086-2108) explains the threat model in detail.
  [verified-by-code] [from-comment]

## The `fmgr_security_definer` trampoline

A single C function (line 633-779) that handles **all** of:
SECURITY DEFINER (`prosecdef`), per-function GUC overrides
(`proconfig`), and `fmgr_hook` plugin entry/exit notifications. On
first call, builds a `fmgr_security_definer_cache` allocated in
`fn_mcxt`:

1. Re-resolves the target function via `fmgr_info_cxt_security(...,
   ignore_security=true)` to avoid infinite recursion.
2. If `prosecdef`, records `proowner` to switch to.
3. If `proconfig` is non-null, parses it into `(names, values)` and
   pre-resolves each name to a `config_handle` for cheap re-set.

On every call:

1. `GetUserIdAndSecContext` to save current identity.
2. `NewGUCNestLevel` if any GUCs to override.
3. `SetUserIdAndSecContext` to the owner if SECURITY DEFINER.
4. Apply each `proconfig` setting via `set_config_with_handle`.
5. `fmgr_hook(FHET_START, …)` if a plugin is registered.
6. `PG_TRY { FunctionCallInvoke + pgstat usage tracking }
   PG_CATCH { fmgr_hook(FHET_ABORT,…); RE_THROW }`.
7. `AtEOXact_GUC(true, save_nestlevel)` to roll back GUCs.
8. Restore userid + sec_context.
9. `fmgr_hook(FHET_END, …)`.

Notable: the comment notes that GUC + userid restoration "doesn't
need" PG_TRY because the surrounding xact/subxact abort handles it
on error — the PG_TRY is purely there to clean up the `fcinfo->flinfo`
link. [verified-by-code] [from-comment]

## Notable invariants / details

- **`fn_oid` is filled last** in `fmgr_info_cxt_security` (line 158-166)
  because some callsites assume "if `fn_oid` is valid, the whole
  struct is valid". A partially-initialised FmgrInfo with a valid
  fn_oid is a bug. [verified-by-code] [from-comment]
- **`fmgr_isbuiltin` fast path** (line 78-95) — directly indexes
  `fmgr_builtins[]` via the auto-generated `fmgr_builtin_oid_index[]`,
  skipping the syscache entirely. Anything past `fmgr_last_builtin_oid`
  takes the slow path. [verified-by-code]
- **`fmgr_security_definer` is taken for any of:** `prosecdef`,
  non-null `proconfig`, or `FmgrHookIsNeeded(functionId)`. Means a
  plugin can intercept ANY function call by hooking `needs_fmgr_hook`
  to return true selectively. [verified-by-code] [from-comment]
- **C-function caching:** `CFuncHash` keyed by Oid stores
  `(fn_xmin, fn_tid, user_fn, inforec)`. On lookup, we verify
  `fn_xmin == HeapTupleHeaderGetRawXmin(procedureTuple)` AND
  `ItemPointerEquals(fn_tid, ctid)` — entry is invalidated if the
  pg_proc row has been updated. [verified-by-code]
- **`fmgr_info_other_lang` recursion:** for SQL or other-language
  functions, recursively `fmgr_info_cxt_security(lan_handler,
  ignore_security=true)`. The trick is that the call handler is
  itself an INTERNAL or C function whose own SECURITY DEFINER
  attributes must not trigger another trampoline. [verified-by-code]
  [from-comment]
- **`PG_FUNCTION_INFO_V1`** is the only supported api_version.
  Older v0 was removed; `fetch_finfo_record` rejects anything else.
  [verified-by-code]
- **GUC nesting via `NewGUCNestLevel` / `AtEOXact_GUC`:** each
  `fmgr_security_definer`-wrapped call gets its own GUC scope.
  Errors inside the call abort the subxact, which the GUC
  machinery uses as the rollback trigger. [verified-by-code]
  [from-comment]
- **Mass repetition of `DirectFunctionCallN`/`FunctionCallN`/
  `OidFunctionCallN`/`CallerFInfoFunctionCallN`:** these are
  cookie-cutter (`N` from 0..9), and likely the largest single
  source of LoC in the file. No macro generation — each variant is
  hand-written. [verified-by-code]
- **`SECURITY_LOCAL_USERID_CHANGE`** is OR'd into sec_context when
  switching userids (line 712-713) — flag bit that the SET
  ROLE/RESET ROLE machinery checks. [verified-by-code]
- **`pgstat_init_function_usage` + `pgstat_end_function_usage`**
  wrap the call only inside `fmgr_security_definer` (line 747, 755).
  Plain-path calls (no SECURITY DEFINER, no proconfig, no hook) are
  charged differently — the comment on line 198-205 explains the
  loss of fine-grained tracking for SECURITY DEFINER calls.
  [verified-by-code] [from-comment]
- **`extern Datum fmgr_security_definer`** (line 69) is declared
  with `extern` "so it's callable via JIT". JIT-generated code can
  call the trampoline directly when the planner has determined a
  function needs it. [verified-by-code] [from-comment]
- **`PG_FUNCTION_INFO_V1` discovery:** info function name is
  `pg_finfo_<funcname>` — `psprintf` builds it (line 463). The
  `pfree(infofuncname)` at line 497 cleans up. [verified-by-code]
- **`fmgr_hook` and `needs_fmgr_hook`** are `PGDLLIMPORT` globals
  (line 41-42). The sepgsql extension is the canonical user.
  [verified-by-code]

## Potential issues

- File-line: fmgr.c:633-779 (`fmgr_security_definer`). The trampoline
  silently ignores `fmgr_hook(FHET_START, ...)` errors — the hook
  doesn't return a status, errors must propagate via ereport. A
  buggy plugin that does cleanup in `FHET_END` only would leak on
  ERROR (line 760-766 only does `FHET_ABORT`). [ISSUE-undocumented-invariant:
  fmgr_hook contract on FHET_ABORT vs FHET_END is subtle (nit)]
- File-line: fmgr.c:206-216. The `fmgr_security_definer` short-circuit
  branch sets `fn_stats = TRACK_FUNC_ALL` (never track), losing the
  ability to charge overhead. Documented in the block comment but
  worth a tag — affects `pg_stat_user_functions` accuracy for SECDEF
  / proconfig / hooked functions. [ISSUE-undocumented-invariant:
  pg_stat_user_functions skews for SECURITY DEFINER functions (nit)]
- File-line: fmgr.c:1752-1789. `OidInputFunctionCall` and friends
  comment self-flags as slow + leaky. No `pfree` of `flinfo` (it's
  on stack) but the internal `fmgr_info` may allocate subsidiary
  data in CurrentMemoryContext that lives until that context resets.
  [ISSUE-leak: documented memory leak in seldom-executed I/O paths
  (nit)]
- File-line: fmgr.c:556-558. `CFuncHash` is unbounded — entries are
  added on demand, never aged. A long-running backend that touches
  many CREATE-FUNCTION-aliased C functions accumulates entries
  forever. Mitigated by xmin/ctid checks invalidating stale entries.
  [ISSUE-leak: CFuncHash has no eviction (nit)]
- File-line: fmgr.c:802-809 (all DirectFunctionCallN). If a callee
  returns NULL but the caller didn't expect one, we `elog(ERROR,
  "function %p returned NULL", func)` — a function-pointer leak
  into the log (ASLR-sensitive). Minor info-disclosure if someone
  hits this in production. [ISSUE-info-disclosure: function pointer
  in ERROR message (nit)]
- File-line: fmgr.c:233. `TextDatumGetCString(prosrcdatum)` then
  `pfree(prosrc)` — but if `fmgr_lookupByName` ERRORs (line 235-239),
  the pfree is skipped. Memory context cleanup eventually reaps it,
  but it's a stylistic leak. [ISSUE-leak: prosrc not pfree'd on
  not-found ereport (nit)]
- File-line: fmgr.c:706. `if (fcache->configNames != NIL) /* Need a
  new GUC nesting level */` — the *only* reason we open a nest
  level. If `proconfig` is empty but `prosecdef` set, no GUC nesting
  happens — fine, because `SetUserIdAndSecContext` is restored
  manually. [verified-by-code]
- File-line: fmgr.c:1611, 1666. `SOFT_ERROR_OCCURRED(escontext)` is
  the soft-error contract. If the input function calls a sub-routine
  that does `ereport(ERROR, ...)` instead of using `errsave`, the
  longjmp escapes and the soft path is bypassed. The compatibility
  matrix of which `_in` functions truly honor soft errors is
  separately documented elsewhere. [ISSUE-undocumented-invariant:
  soft-error compliance is per-input-function (maybe)]
- File-line: fmgr.c:2073-2076. `get_fn_opclass_options` raises ERROR
  with `ERRCODE_INVALID_PARAMETER_VALUE` if called without options
  set — callers must `has_fn_opclass_options` first. Mismatch leads
  to ERROR. [ISSUE-undocumented-invariant: precondition on
  get_fn_opclass_options (nit)]
- File-line: fmgr.c:2098-2108. `CheckFunctionValidatorAccess`
  comment notes "checking the EXECUTE privilege on the function is
  often superfluous, because most users can clone the function" —
  acknowledged trust gap. [ISSUE-undocumented-invariant: validator
  privilege check has documented bypass via cloning (nit)]
- File-line: fmgr.c:1925-1931. The `ScalarArrayOpExpr` argnum==1
  special-case calls `get_base_element_type` — which may return
  InvalidOid if the type isn't an array. The callsite doesn't check.
  In practice the planner guarantees arg 1 is an array; a malformed
  expr would return InvalidOid (the documented "info unavailable"
  signal). [verified-by-code]
- File-line: fmgr.c:531-532. `CFuncHash` validity check uses
  `HeapTupleHeaderGetRawXmin` — but if the pg_proc row was vacuumed
  with FREEZE, the raw xmin might be FrozenTransactionId. Cache
  entries created pre-freeze would mismatch. Not a correctness
  issue (the cache just refetches), but a perf nit. [ISSUE-style:
  cache invalidation on FREEZE causes refetch (nit)]
- File-line: fmgr.c:670. `fcache->userid = procedureStruct->proowner`
  — captured at first-call cache build. If ALTER FUNCTION ... OWNER
  TO runs after caching, the cached owner is stale. Syscache
  invalidation should rebuild via `fn_extra = NULL`, but
  `fmgr_security_definer` checks `fn_extra` to decide whether to
  rebuild — fine because the broader fmgr_info invalidation reruns.
  [verified-by-code]
- File-line: fmgr.c:725-728. `set_config_with_handle` is called for
  each proconfig — passing `GUC_ACTION_SAVE` so AtEOXact_GUC restores.
  Failure inside set_config_with_handle (e.g. bad enum value) would
  ERROR with the partial proconfig already set; subxact abort
  rolls back. [verified-by-code]
