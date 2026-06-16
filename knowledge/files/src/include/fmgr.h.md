# `src/include/fmgr.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~857
- **Source:** `source/src/include/fmgr.h`

The function manager API — included by every module that **defines or
calls** an fmgr-callable function. Defines the V1 calling convention
(`PG_FUNCTION_ARGS` / `PG_GETARG_*` / `PG_RETURN_*`), the `FmgrInfo` /
`FunctionCallInfoBaseData` machinery, `PG_FUNCTION_INFO_V1` /
`PG_MODULE_MAGIC[_EXT]` for loadable modules, and the
`DirectFunctionCall*` / `OidFunctionCall*` / `FunctionCall*` calling
families. [verified-by-code]

## API / declarations

### Calling convention

- `PGFunction` (`fmgr.h:40`) — `typedef Datum (*PGFunction)
  (FunctionCallInfo fcinfo);`. Every V1 SQL function has this
  signature.
- `FmgrInfo` (`fmgr.h:56-67`) — the per-call **cached lookup**:
  `fn_addr`, `fn_oid`, `fn_nargs`, `fn_strict`, `fn_retset`,
  `fn_stats`, `fn_extra` (caller-owned), `fn_mcxt`, `fn_expr`.
  Comment: "If the same function is to be called multiple times,
  the lookup need be done only once and the info struct saved for
  re-use" (`fmgr.h:43-46`).
- `FunctionCallInfoBaseData` (`fmgr.h:85-96`) — the per-call argument
  struct. Renamed from `*Data` to `*BaseData` deliberately to break
  pre-v12 extensions that allocated `FunctionCallInfoData` itself
  (would have silently lacked space for `args`).
  `FIELDNO_FUNCTIONCALLINFODATA_ISNULL=4`,
  `FIELDNO_FUNCTIONCALLINFODATA_ARGS=6` — exposed for JIT.
- `SizeForFunctionCallInfo(nargs)` (`fmgr.h:102-104`) — required
  allocation size including `args[nargs]`.
- `LOCAL_FCINFO(name, nargs)` (`fmgr.h:110-118`) — stack-alloc an
  fcinfo with the right size via a union trick. The trick is required
  because a bare struct can't safely embed VLA.
- `InitFunctionCallInfoData(...)` macro (`fmgr.h:150-158`).
- `FunctionCallInvoke(fcinfo)` (`fmgr.h:172`) — `(*fcinfo->flinfo->fn_addr)(fcinfo)`.

### Per-function macros (`fmgr.h:175-377`)

- `PG_FUNCTION_ARGS` = `FunctionCallInfo fcinfo`.
- `PG_GET_COLLATION()`, `PG_NARGS()`, `PG_ARGISNULL(n)`.
- Detoasting (`fmgr.h:212-249`):
  - `pg_detoast_datum(datum)` — full detoast (4-byte header).
  - `pg_detoast_datum_copy(datum)` — always palloc'd copy.
  - `pg_detoast_datum_slice(datum, first, count)` — partial.
  - `pg_detoast_datum_packed(datum)` — leaves 1-byte-header datums
    as-is; **caller must use VARSIZE_ANY/VARDATA_ANY**, possibly
    unaligned.
  - `PG_DETOAST_DATUM[_COPY|_SLICE|_PACKED]` wrap them.
- `PG_FREE_IF_COPY(ptr, n)` (`fmgr.h:260-264`) — pfree only if the
  detoast actually copied.
- `PG_GETARG_*` family (`fmgr.h:268-339`): `_INT32`, `_UINT32`,
  `_INT16`, `_UINT16`, `_CHAR`, `_BOOL`, `_OID`, `_OID8`, `_POINTER`,
  `_CSTRING`, `_NAME`, `_TRANSACTIONID`, `_FLOAT4`, `_FLOAT8`,
  `_INT64`, `_RAW_VARLENA_P`, `_VARLENA_P`, `_VARLENA_PP`,
  `_BYTEA_PP/P_COPY/P_SLICE`, `_TEXT_PP/...`, `_BPCHAR_PP/...`,
  `_VARCHAR_PP/...`, `_HEAPTUPLEHEADER[_COPY]`. The `_PP` suffix
  means "packed pointer" — possibly unaligned, 1-byte-header
  preserved. Most code should prefer `_PP` over the obsolescent
  `_P` variants (`fmgr.h:326-330`).
- `PG_HAS_OPCLASS_OPTIONS()` / `PG_GET_OPCLASS_OPTIONS()` (`fmgr.h:342-343`).
- `PG_RETURN_NULL()` / `PG_RETURN_VOID()` / `PG_RETURN_*` family.

### Module / ABI machinery

- `Pg_finfo_record { int api_version; }` (`fmgr.h:396-400`) — current
  api_version is 1; V0 is no longer supported. Version > 1 may add
  fields.
- `PG_FUNCTION_INFO_V1(funcname)` (`fmgr.h:417-426`) — generates a
  per-function `pg_finfo_<funcname>` info function returning version
  1. Required for every V1 dynamically-loaded function.
- `_PG_init` declared as `PGDLLEXPORT void` (`fmgr.h:436`) — the
  central declaration avoids each extension having to mark it
  PGDLLEXPORT. Comment notes pre-fmgr.h `_PG_init` decls in extensions
  break on Windows.
- `Pg_abi_values { version, funcmaxargs, indexmaxkeys, namedatalen,
  float8byval, abi_extra[32]; }` (`fmgr.h:468-476`) — compared with
  memcmp(); MUST contain no padding.
- `Pg_magic_struct { len, abi_fields, name, version }` (`fmgr.h:479-486`).
- `PG_MODULE_ABI_DATA` / `PG_MODULE_MAGIC_DATA` / `PG_MODULE_MAGIC` /
  `PG_MODULE_MAGIC_EXT(...)` — required exactly once per extension.
- `StaticAssertDecl(sizeof(FMGR_ABI_EXTRA) <= sizeof(((Pg_abi_values
  *) 0)->abi_extra), ...)` at `fmgr.h:510` — prevents fork-derived
  FMGR_ABI_EXTRA strings from exceeding 32 bytes silently.

### Calling families (`fmgr.h:552-743`)

Three families × N-argument variants × Coll suffix:
- `DirectFunctionCall1Coll`..`9Coll` — call PGFunction directly,
  no FmgrInfo. Comment: arguments may NOT be NULL.
- `CallerFInfoFunctionCall1/2` (`fmgr.h:602-605`) — use caller's
  flinfo (only fn_extra/fn_mcxt are usable by callee).
- `FunctionCall0Coll..9Coll` — use a previously-resolved FmgrInfo.
- `OidFunctionCall0Coll..9Coll` — resolve OID then call.
- Per-family `Coll`-suffix-less macros (`fmgr.h:688-743`) pass
  `InvalidOid` as collation; kept for backward source compat.

### I/O conv (`fmgr.h:747-766`)

- `InputFunctionCall(flinfo, str, typioparam, typmod)` — hard error
  on failure.
- `InputFunctionCallSafe(flinfo, str, typioparam, typmod, escontext,
  &result)` — returns false on soft-error capture via escontext.
- `DirectInputFunctionCallSafe(...)` — same but direct.
- `OidInputFunctionCall`, `OutputFunctionCall`,
  `OidOutputFunctionCall`, `ReceiveFunctionCall`,
  `OidReceiveFunctionCall`, `SendFunctionCall`,
  `OidSendFunctionCall`.

### Misc fmgr / dfmgr surface

- `fmgr_internal_function`, `get_fn_expr_rettype`,
  `get_fn_expr_argtype`, `get_call_expr_argtype`,
  `get_fn_expr_arg_stable`, `get_call_expr_arg_stable`,
  `get_fn_expr_variadic`, `get_fn_opclass_options`,
  `has_fn_opclass_options`, `set_fn_opclass_options`,
  `CheckFunctionValidatorAccess`.
- `DynamicFileList` opaque + `Dynamic_library_path` GUC handle.
- `substitute_path_macro`, `find_in_path`, `load_external_function`,
  `lookup_external_function`, `load_file(restricted)`,
  `get_first_loaded_module`/`get_next_loaded_module`/
  `get_loaded_module_details`, `find_rendezvous_variable`,
  `EstimateLibraryStateSpace`/`SerializeLibraryState`/
  `RestoreLibraryState` — the per-extension state machinery for
  parallel-worker library handoff.

### Aggregate-context inspection (`fmgr.h:817-828`)

- `AGG_CONTEXT_AGGREGATE=1`, `AGG_CONTEXT_WINDOW=2`.
- `AggCheckCallContext(fcinfo, &aggcontext)` — returns 0 / 1 / 2.
- `AggGetAggref`, `AggGetTempMemoryContext`, `AggStateIsShared`,
  `AggRegisterCallback`.

### Plugin hook (`fmgr.h:830-855`)

- `FmgrHookEventType { FHET_START, FHET_END, FHET_ABORT }`.
- `needs_fmgr_hook` / `fmgr_hook` PGDLLIMPORT — intended for
  security-policy plugins (sepgsql is the in-tree user).
- `FmgrHookIsNeeded(fn_oid)` macro.

## Notable invariants / details

- `fcinfo->isnull` MUST be reset to false before each call when an
  fcinfo is re-used (`fmgr.h:167-170`). Failure → silently NULL results.
  [from-comment]
- Strict functions: caller verifies no NULL args; callee can skip
  `PG_ARGISNULL`. Non-strict callees MUST call `PG_ARGISNULL(n)`
  before `PG_GETARG_*(n)` (`fmgr.h:206-209`). Calling `PG_GETARG_*`
  on a null arg = undefined behavior. [from-comment]
- `LOCAL_FCINFO` requires nargs to be a compile-time constant — its
  expansion uses `char fcinfo_data[SizeForFunctionCallInfo(nargs)]`,
  which is not technically a VLA (PG forbids those) only if nargs is
  constant. [verified-by-code]
- `Pg_abi_values` is compared with `memcmp` so it MUST be padding-free
  (`fmgr.h:458-460`). On any platform where `int` is 4 bytes, the 5
  ints + 32-byte char array packs cleanly — but adding a `bool` or
  short would introduce padding. [from-comment]
  [ISSUE-undocumented-invariant: no compile-time
  `StaticAssert(sizeof(Pg_abi_values) ==
  expected_packed_size)`; future field additions could silently break
  ABI compatibility detection (likely)]
- `PG_MODULE_MAGIC` MUST appear exactly once per shared module
  (`fmgr.h:443-449`). If absent, `load_external_function` rejects
  with "incompatible library". If duplicated, linker error.
- `_PG_init` declaration as `PGDLLEXPORT` (`fmgr.h:436`) — the
  comment-noted hazard: if an extension's own header is included
  BEFORE `fmgr.h` and declares `_PG_init` without `PGDLLEXPORT`,
  Windows builds fail. Existing extensions are immune only because
  fmgr.h is included first in the typical chain. [from-comment]
- `PG_DETOAST_DATUM_PACKED` returns a **possibly-unaligned pointer**
  (`fmgr.h:247`). Code using it must use `VARSIZE_ANY`/`VARDATA_ANY`,
  and must never cast to `int16*`/`int32*` for direct field access.
- `fn_extra` is the official caller-owned slot for per-FmgrInfo
  caching; conventional use is to allocate state in `fn_mcxt` on
  the first call. [from-comment]
- `FmgrHook` plugin entry points (`fmgr.h:830-855`) are essentially
  arbitrary-code-execution on every function call — sepgsql uses
  them for MAC. A buggy hook can crash the backend or leak.
  [ISSUE-security: fmgr_hook is unrestricted by superuser — any
  preloaded library can install it (likely)]

## Potential issues

- `fmgr.h:78-83` — `FunctionCallInfoBaseData` was renamed to break
  pre-v12 stack-allocated callers. New extension authors who allocate
  it by sizeof rather than `SizeForFunctionCallInfo` still get a
  silent buffer-too-small for >0 args. [ISSUE-api-shape: stack
  allocation of `FunctionCallInfoBaseData` by sizeof silently
  under-allocates `args[]` (likely)]
- `fmgr.h:166-170` — the "reset isnull" rule is comment-only. A
  caller that re-uses fcinfo without resetting isnull silently
  produces NULL results. [ISSUE-undocumented-invariant: isnull
  reset on re-use is comment-only; no Assert (maybe)]
- `fmgr.h:282-283` — `PG_GETARG_FLOAT4/_FLOAT8` use the union trick
  via `DatumGetFloat4/8`; calling these macros on a Datum that
  doesn't actually contain a float silently returns garbage. No
  static check possible. [ISSUE-api-shape: PG_GETARG_FLOATx has no
  type-system protection (nit)]
- `fmgr.h:445-449` — `PG_MODULE_MAGIC` location is one-per-module;
  multi-source-file modules with the macro in a header get either
  link error (gcc) or silent merging (LTO). [ISSUE-api-shape:
  PG_MODULE_MAGIC placement contract not enforced (nit)]
- `fmgr.h:475` — `abi_extra[32]` is fixed-size; the `StaticAssertDecl`
  at line 510 guards length but not encoding. A fork that puts UTF-8
  with embedded NULs would error-message-leak garbage.
  [ISSUE-style: abi_extra should be ASCII-printable (nit)]
- `fmgr.h:563-682` — the Coll-suffix family has 9 arities; adding a
  10-arg variant requires hand-editing dozens of macros. Hard cap on
  `FUNC_MAX_ARGS=100` (from `pg_config_manual.h`) but
  DirectFunctionCallN tops out at 9. [ISSUE-api-shape:
  DirectFunctionCall family limited to 9 args (nit)]
- `fmgr.h:830-855` — `fmgr_hook` is a single global pointer; no
  chaining discipline at header level. Two preloaded libraries that
  both install it will silently overwrite each other.
  [ISSUE-defense-in-depth: fmgr_hook lacks chained-hook idiom in
  header docs (likely)]
- `fmgr.h:798` — `load_file(restricted)` second arg is a bool with
  no enum naming; calls with `false` vs `true` are easy to swap.
  [ISSUE-style: `load_file` restricted parameter is bare bool (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
