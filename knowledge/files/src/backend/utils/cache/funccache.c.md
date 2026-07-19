# src/backend/utils/cache/funccache.c

## Purpose

Cross-language cache for compiled "function" state — used by SQL-language
functions, PL/pgSQL, and any other PL that wants per-`pg_proc` compiled state
keyed by the actual argument types of the call. Each entry is keyed by
function OID *plus* the concrete (post-polymorphic-resolution) input arg types,
so a polymorphic function gets one entry per (oid, argtype-vector) shape.
[from-comment] (`funccache.c:6-14`)

## Role in PG

- Holds a backend-lifetime hash table (`cfunc_hashtable`, `funccache.c:39`) in
  `TopMemoryContext` (`funccache.c:59-74`).
- Language frontends (e.g. `pl_comp.c`, `functions.c`) call
  `cached_function_compile()` to either find or compile a `CachedFunction`
  subtype; the language supplies its own `ccallback` (compile) and
  `dcallback` (delete) plus its struct size. [verified-by-code]
  (`funccache.c:479-634`)
- Validation path (`forValidator=true`) is also supported — used by
  `CREATE FUNCTION ... AS ... LANGUAGE plpgsql` time syntax check.

## Key functions

- `cached_function_compile(fcinfo, function, ccallback, dcallback, cacheEntrySize, includeResultType, forValidator)` —
  central entry point. Looks up by hashkey, validates against `pg_proc`
  `xmin`/`tid` (`funccache.c:524-525`), compiles via `ccallback` under a
  `PG_TRY`/`PG_CATCH` that pfrees a freshly-allocated struct on failure
  (`funccache.c:598-611`).
- `compute_function_hashkey(fcinfo, procStruct, hashkey, …)` — fills
  `funcOid`, `isTrigger`, `isEventTrigger`, `cacheEntrySize`, `trigOid`
  (when called as DML trigger, `funccache.c:279-284`), `inputCollation`,
  resolved argtypes, and optionally `callResultType` from
  `get_call_result_type()` for composite returns
  (`funccache.c:317-332`).
- `cfunc_resolve_polymorphic_argtypes()` — wraps
  `resolve_polymorphic_argtypes()` with three twists: erroring on
  unresolved polymorphics, treating input `RECORD`/`RECORDARRAY` as
  polymorphic so each composite gets its own entry, and substituting
  INT4/INT4ARRAY/INT4RANGE/INT4MULTIRANGE in validator mode
  (`funccache.c:347-416`).
- `cfunc_hash`/`cfunc_match` — custom hash+match because the key contains
  a `TupleDesc *` (`callResultType`) compared with `equalRowTypes` instead
  of memcmp (`funccache.c:84-139`).
- `delete_function` — invoked when stale pg_proc detected; defers
  subsidiary storage release if `use_count != 0` (recursive call in
  progress) and accepts the leak (`funccache.c:432-445`).

## State / globals

- `cfunc_hashtable` — single backend-wide HTAB; entries' callbacks
  (`dcallback`) are responsible for language-specific cleanup.
- `fn_extra` back-link convention: caller saves
  `cached_function_compile`'s result in `fmgr_info.fn_extra`; on next
  call the same pointer is passed back as `function`, skipping the hash
  lookup (`funccache.c:505-519`).

## Phase D notes

- Cache is **per-backend**, never shared. No cross-session leak surface.
  Volatile functions remain correct because the cached entity is the
  compiled plan/parse tree, not the result. [inferred]
- Invalidation is `xmin`/`tid` based — when `ALTER FUNCTION` /
  `REPLACE FUNCTION` swaps the pg_proc row, the next compile sees the
  mismatch and rebuilds. Recursive in-flight calls keep running on the
  old definition until they exit (then the entry is leaked rather than
  cleaned up, `funccache.c:542-554`). [from-comment]
- Hash includes `cacheEntrySize` so different PLs (each calling with
  their own struct size) don't collide (`funccache.c:264-265`).

## Potential issues

- [ISSUE-correctness: A failed compile that reuses an existing
  `function` struct (`new_function == false`) re-`memset`s it to zero
  before calling `ccallback` (`funccache.c:585-588`), but on
  `PG_CATCH` it does NOT free — leaving a zeroed struct in
  `TopMemoryContext` plus a dangling hash entry if `cfunc_hashtable_delete`
  also ran. Mitigated because `delete_function` clears `fn_hashkey`,
  but warrants verification (maybe)]
- [ISSUE-undocumented-invariant: callback `dcallback` MUST be
  long-jmp safe — it's called from `delete_function` which runs inside
  invalidation callbacks (relcache invalidation, etc.). Not stated in
  comments (low)]
- [ISSUE-state-transition: when callResultType allocation fails
  (`funccache.c:188-195`), the entry is silently left with NULL
  callResultType "which will probably never match anything" — i.e. a
  permanently-unreferenced hash entry. Effectively a slow leak under
  OOM pressure (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
