# utils/funccache.h — language-agnostic compiled-function cache

Source: `source/src/include/utils/funccache.h` (134 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Shared cache infrastructure used by PL/pgSQL and SQL-language functions to amortize compilation across calls. Key-by hash; invalidate when pg_proc row changes (xmin/ctid).

## Public API

- Callbacks (`funccache.h:35-45`): `CachedFunctionCompileCallback` (compile a fresh entry), `CachedFunctionDeleteCallback` (free subsidiary data on eviction).
- `CachedFunctionHashKey` (`funccache.h:52-99`): funcOid + isTrigger + isEventTrigger + cacheEntrySize + trigOid + inputCollation + nargs + callResultType (tupdesc for composite returns) + argtypes[FUNC_MAX_ARGS].
- `CachedFunction` (`funccache.h:106-118`): fn_hashkey backpointer + fn_xmin/fn_tid (invalidation watch) + dcallback + use_count.
- `cached_function_compile(fcinfo, function, ccallback, dcallback, cacheEntrySize, includeResultType, forValidator)` (`funccache.h:120-126`).
- `cfunc_resolve_polymorphic_argtypes(numargs, argtypes, argmodes, call_expr, forValidator, proname)` (`funccache.h:127-132`).

## Invariants

- **INV-hashkey-pad-bytes-zeroed** [from-comment, `funccache.h:59`]: "be careful that pad bytes in this struct get zeroed!" because the hash is taken over the raw struct memory. memset to 0 before populating.
- **INV-cacheEntrySize-in-key** [from-comment, `funccache.h:62-66`]: covers CREATE OR REPLACE FUNCTION changing implementation language. Two languages can both use funccache but need different-sized entries.
- **INV-trigOid-in-key-for-DML-triggers** [from-comment, `funccache.h:69-74`]: same trigger function compiled per-trigger because rowtype/transition-table names differ.
- **INV-inputCollation-in-key** [from-comment, `funccache.h:77-82`]: different collations produce different param-Datum interpretations; must split cache entries.
- **INV-callResultType-only-for-composite** [verified-by-code, `funccache.h:89-92`]: NULL for scalar-returning functions.
- **INV-xmin-ctid-invalidation** [verified-by-code, `funccache.h:110-112`]: when the pg_proc row's xmin or ctid changes, the cache entry is stale. Caller's `dcallback` runs at eviction.
- **INV-changes-below-this-line-fix-hashing** [from-comment, `funccache.h:87`]: ordering of fields below this comment matters for the hash computation.

## Trust-boundary / Phase-D surface

- **Hash over raw struct memory** (`funccache.h:59`): violates the "no information leak via padding" rule weakly — the leak is intra-process only (pad bytes seeded from stack), but if a value is misremembered then cache lookups are wrong. The fix is the comment + memset discipline.
- **`forValidator` flag** (`funccache.h:38`): set during CREATE FUNCTION validation; compilation may want to be more lenient about errors (e.g. don't fail on a missing table that the user is about to create). Callers must thread it correctly.
- **`use_count` is just a counter** (`funccache.h:117`) — no eviction policy in the header; eviction is xmin-driven, not LRU.

## Cross-refs

- `source/src/backend/utils/cache/funccache.c` — implementation.
- `source/src/pl/plpgsql/src/pl_comp.c`, `pl_handler.c` — primary consumer.

## Issues

- `[ISSUE-INVARIANT: pad-byte-zero contract is by-comment-only (medium)]` — `funccache.h:59`. A `StaticAssertStmt` that `sizeof(CachedFunctionHashKey)` has no padding would catch field-reorder regressions.
- `[ISSUE-DOC: callResultType lifetime (low)]` — tupdesc lifetime ownership not surfaced; whose context holds it?

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-cache.md](../../../../subsystems/utils-cache.md)
