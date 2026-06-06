---
source_url: https://www.postgresql.org/docs/current/xfunc-c.html
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — C-Language Functions (xfunc-c)

The canonical contract for a hand-written C function reachable from SQL: the
Version-1 fmgr ABI, Datum representation, the varlena/TOAST rules, null and
memory-context discipline, and how the dynamic loader finds your `.so`. This is
the prose the `fmgr-and-spi` and `extension-development` skills operationalize.

## The Version-1 calling convention

- **Every SQL-callable C function is `Datum funcname(PG_FUNCTION_ARGS)`** —
  one fixed C signature regardless of the SQL-level argument list; arguments
  come out via `PG_GETARG_*(n)`, results go back via `PG_RETURN_*()`. [from-docs]
- **`PG_FUNCTION_INFO_V1(funcname);` is mandatory for dynamically-loaded
  functions**, in the same source file. Built-in functions are assumed v1 and
  don't need it. The macro emits the metadata fmgr uses to call you safely
  (incl. TOAST handling). [from-docs]
- **`DirectFunctionCall`N`(cfunc, ...)` calls another v1 function by C name**
  (vs `OidFunctionCall`N`()` by OID); all args/returns are `Datum` and **NULL
  args are not allowed** on this path. Collation-sensitive callees need the
  `...Coll` variant, e.g. `DirectFunctionCall2Coll(text_starts_with,
  PG_GET_COLLATION(), ...)`. [from-docs]

## Datum, by-value vs by-reference

- **Datum is opaque; the `PG_GETARG_*` / `PG_RETURN_*` macros hide whether a
  type is by-value or by-reference.** `INT32` is genuinely by-value;
  `FLOAT8` is *by-reference under the hood* but the macros paper over it; a
  `POINT` is `_P` (pointer) and you must `palloc` the result. [from-docs]
- **By-value types may only be 1, 2, 4, or 8 bytes and must be the same size on
  every architecture.** Avoid `long` (4 bytes on some platforms, 8 on others);
  use `int`/`int32`. PG C naming: `intXX` = XX *bits*, so C `int8` = 1 byte;
  beware SQL `int8` maps to C `int64`. [from-docs]
- **NEVER modify a pass-by-reference input in place.** The pointer may aim
  directly into a shared disk buffer; mutating it corrupts on-disk data. (The
  only sanctioned exception is in user-defined aggregate transition functions.)
  [from-docs]

## Variable-length (varlena / TOAST) types

- **A varlena type starts with a 4-byte length word; set it ONLY via
  `SET_VARSIZE()`, never by direct assignment.** The length includes the header
  itself. `VARHDRSZ` (= `sizeof(int32)`) is the header size. [from-docs]
- **Canonical allocation pattern:** `palloc(VARHDRSZ + n)` →
  `SET_VARSIZE(p, VARHDRSZ + n)` → `memcpy(VARDATA(p), src, n)`. Use the
  `VARSIZE_ANY_EXHDR()` / `VARDATA_ANY()` accessors to handle both long- and
  short-header (1-byte) varlena layouts transparently. [from-docs]
- **Detoast inputs that may be compressed/out-of-line** before reading their
  bytes (`PG_GETARG_*_P` does this for you; raw `PG_DETOAST_DATUM` exists for
  manual paths). [from-docs]
- **Zero padding bytes** (`palloc0` or `memset`) in any fixed-length composite
  struct: even with all *fields* assigned, alignment padding holds garbage, and
  the planner/hash-join/hash-index machinery uses **bitwise** equality on
  constants — garbage padding makes equal values compare unequal. [from-docs]

## Nulls and memory

- **Declare the function `STRICT`** to have the system short-circuit a NULL
  result whenever any argument is NULL — then you may skip `PG_ARGISNULL`.
  A non-strict function **must** call `PG_ARGISNULL(n)` *before* the
  corresponding `PG_GETARG_*`. Return SQL NULL with `PG_RETURN_NULL()`. [from-docs]
- **Use `palloc`/`pfree`, never `malloc`/`free`.** `palloc` memory in the
  current (per-call) context is auto-freed at transaction/query end, so you get
  leak-safety for free — but it also means cross-call survival needs care.
  [from-docs]
- **Set-returning functions keep cross-call state in
  `funcctx->multi_call_memory_ctx`.** The call-time context is transient and
  cleared between value-per-call returns; allocate persistent structures (and
  copies of any detoasted args you stash in `user_fctx`) in
  `multi_call_memory_ctx` during `SRF_FIRSTCALL_INIT()` via
  `MemoryContextSwitchTo`. It's freed automatically at query end. [from-docs]

## Composite types

- **Read a composite arg** via `PG_GETARG_HEAPTUPLEHEADER(n)` then
  `GetAttributeByName(t, "field", &isnull)` / `GetAttributeByNum(...)`; always
  check `isnull`, then `DatumGetXxx()` the result. [from-docs]
- **Return a composite** by obtaining a `TupleDesc` from
  `get_call_result_type(fcinfo, NULL, &tupdesc)`, then either build from a Datum
  array (`BlessTupleDesc()` → `heap_form_tuple()`) or from C strings
  (`TupleDescGetAttInMetadata()` → `BuildTupleFromCStrings()`), and finally
  `HeapTupleGetDatum(tuple)`. [from-docs]
- **Polymorphic (`anyelement`/`anyarray`) functions discover real types at
  runtime** via `get_fn_expr_argtype(flinfo, argnum)` (zero-based),
  `get_fn_expr_rettype(flinfo)`, and `get_fn_expr_variadic()`; `InvalidOid`
  means unavailable. [from-docs]

## Dynamic loading + module init

- **`PG_MODULE_MAGIC;` is required, exactly once, after including `fmgr.h`.**
  The magic block lets the server reject a `.so` compiled against an
  incompatible major version; without it a load may "succeed" then misbehave
  unpredictably. `PG_MODULE_MAGIC_EXT(.name=, .version=)` adds metadata visible
  via `pg_get_loaded_modules()`. [from-docs]
- **`_PG_init()` runs once, immediately on first load** (no args, void return);
  there is **no unload** — the library stays mapped for the session, so a reload
  needs a fresh session. [from-docs]
- **Library search order:** absolute path → `$libdir` (expands to the build-time
  pkglibdir, see `pg_config --pkglibdir`) → `dynamic_library_path` (when no
  directory component) → name as-given (unreliable); on miss, append the
  platform shared-lib extension and retry. The name is stored *literally* in the
  catalog and re-resolved on reload. [from-docs]
- **The server's OS user must be able to *traverse* the whole path** to the
  `.so` (execute on dirs); a directory not executable by `postgres` is a common
  silent-failure cause. [from-docs]

## Writing + compiling

- **`#include "postgres.h"` FIRST**, before any system/user header (it pulls in
  `elog.h` and `palloc.h`); other-header-first ordering causes portability
  breakage. Object-file symbol names must not collide with server symbols.
  [from-docs]
- **Shared objects need PIC:** `-fPIC` (GCC/most Unix) or `-KPIC` (Sun cc) to
  compile, `-shared` / `-G` / macOS `-bundle -flat_namespace -undefined suppress`
  to link; PGXS or libtool hides the platform spread. [from-docs]

## Links into corpus

- [[knowledge/idioms/fmgr.md]] — the fmgr ABI in idiom form.
- [[knowledge/idioms/memory-contexts.md]] — palloc/context discipline this
  chapter depends on.
- [[knowledge/files/src/backend/utils/fmgr/funcapi.c.md]] — SRF + composite +
  polymorphic helper machinery (`get_call_result_type`, SRF macros).
- [[knowledge/files/src/backend/utils/fmgr/dfmgr.c.md]] — the dynamic loader +
  `_PG_init` + `$libdir`/`dynamic_library_path` resolution.
- [[knowledge/idioms/catalog-conventions.md]] — registering the function in
  pg_proc so SQL can reach it.
- Skill: `fmgr-and-spi` — PG_FUNCTION_INFO_V1, PG_GETARG/RETURN, SRF modes.
- Skill: `extension-development` — PG_MODULE_MAGIC, `_PG_init`, build glue.
- Skill: `memory-contexts` — context selection for cross-call data.

## Confidence note

All claims `[from-docs]` (C-Language Functions chapter, fetched 2026-06-05).
Section numbers vary by release, so claims cite topic rather than number; the
corpus cross-links carry the `source/...:line` verification for the named
helpers.
