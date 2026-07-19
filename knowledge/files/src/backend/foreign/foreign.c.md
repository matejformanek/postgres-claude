# `src/backend/foreign/foreign.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~890
- **Source:** `source/src/backend/foreign/foreign.c`

The "look it up in the catalog" layer for foreign-data-wrappers,
servers, and user mappings. Backs SQL DDL (CREATE/ALTER FOREIGN
DATA WRAPPER etc.) by handing FDW C code easy-to-use accessor
functions, and exposes a couple of SQL-callable utilities
(`postgresql_fdw_validator`, `pg_options_to_table`). Also home to
`GetExistingLocalJoinPath` — the planner helper used by FDWs to
emit a local fall-back plan for EPQ recheck on pushed-down joins.
[verified-by-code]

The file is "look up an OID → palloc a struct from syscache → return
it" repeated five times for FDW, server, user mapping, foreign table,
foreign column. Plus the FdwRoutine plumbing (caching the handler's
function-pointer struct on the relcache entry).

## API / entry points

- **FDW lookup:** `GetForeignDataWrapper(oid)`,
  `GetForeignDataWrapperExtended(oid, flags)`,
  `GetForeignDataWrapperByName(name, missing_ok)`.
  `FDW_MISSING_OK` controls error vs NULL.
  [verified-by-code §foreign.c:38-107]
- **Server lookup:** `GetForeignServer(oid)`,
  `GetForeignServerExtended(oid, flags)`,
  `GetForeignServerByName(name, missing_ok)`.
  Resolves server-level options into a `List *` via
  `untransformRelOptions`. [verified-by-code §foreign.c:113-230]
- **User mapping:** `GetUserMapping(userid, serverid)` — falls back
  to public mapping (userid = `InvalidOid`) if user-specific not
  found, raising ERROR if neither exists. [verified-by-code §foreign.c:232-284]
- **Foreign table:** `GetForeignTable(relid)` — server OID + table-
  level options. [verified-by-code §foreign.c:286-322]
- **Foreign column:** `GetForeignColumnOptions(relid, attnum)` — list
  of DefElem for the named column's per-attribute options.
  [verified-by-code §foreign.c:324-355]
- **FdwRoutine plumbing:**
  - `GetFdwRoutine(fdwhandler)` — calls the C handler via
    `OidFunctionCall0`, checks return type is `T_FdwRoutine`.
    [verified-by-code §foreign.c:357-385]
  - `GetForeignServerIdByRelId(relid)` — relcache lookup → server OID.
  - `GetFdwRoutineByServerId(serverid)` / `GetFdwRoutineByRelId(relid)`.
  - **`GetFdwRoutineForRelation(rel, makecopy)`** — preferred caching
    entry. First call materializes the FdwRoutine into
    `CacheMemoryContext` and stashes it on `rel->rd_fdwroutine`;
    subsequent calls return that cached pointer (or a fresh copy if
    `makecopy`). The cached struct is invalidated by relcache resets.
    [verified-by-code §foreign.c:473-504, from-comment §foreign.c:466-471]
- **IMPORT FOREIGN SCHEMA filter:**
  `IsImportableForeignTable(tablename, stmt)` — applies
  LIMIT TO / EXCEPT / ALL on a `RangeVar` list.
  [verified-by-code §foreign.c:514-545]
- **SQL-callable utilities:**
  - `pg_options_to_table(PG_FUNCTION_ARGS)` — converts a text[]
    options array into a 2-col tuplestore (option, value). Used by
    information_schema and pg_dump.
    [verified-by-code §foreign.c:553-590]
  - `postgresql_fdw_validator(PG_FUNCTION_ARGS)` — DEPRECATED, only
    for testing. Validates libpq-style options against a hard-coded
    list (`libpq_conninfo_options[]`) that includes `host`, `port`,
    `sslmode`, etc. Reports unknown options with a closest-match
    hint via `ClosestMatchState`.
    [verified-by-code §foreign.c:597-703, from-comment §foreign.c:651-654]
- **OID lookups (by name):** `get_foreign_data_wrapper_oid(name, missing_ok)`,
  `get_foreign_server_oid(name, missing_ok)`. Use
  `GetSysCacheOid1` with `FOREIGNDATAWRAPPERNAME`/`FOREIGNSERVERNAME`.
  [verified-by-code §foreign.c:712-747]
- **`GetExistingLocalJoinPath(joinrel)`** — pushed-down-join EPQ
  fallback. Walks `joinrel->pathlist` for an unparameterized
  HashJoin/NestLoop/MergeJoin; if the inner or outer is itself a
  ForeignPath corresponding to a pushed-down join, swaps in
  `fdw_outerpath` so the EPQ plan is built from local joins all the
  way down. For MergeJoin, clears `outersortkeys` / `innersortkeys`
  if the new sub-path already provides the needed ordering. Returns
  a SHALLOW copy because the planner may free the original.
  [verified-by-code §foreign.c:772-891, from-comment §foreign.c:749-771]

## Notable invariants / details

- **All `Get*` accessors are SysCache-backed**, never direct table
  scans, so they're cheap after warmup. The returned struct is
  palloc'd in `CurrentMemoryContext` and contains pstrdup'd names —
  caller owns the memory.
  [verified-by-code §foreign.c:51-91 pattern repeated everywhere]
- **`GetUserMapping` public-fallback:** the function searches for
  `(userid, serverid)`; on miss it searches `(InvalidOid, serverid)`
  (the PUBLIC mapping). If neither exists, errors with the user-
  visible name from `GetUserNameFromId`. This is the only file where
  the "no user mapping defined" error originates.
  [verified-by-code §foreign.c:232-284]
- **FdwRoutine cache reuse:** the caller of
  `GetFdwRoutineForRelation` MUST NOT keep the returned pointer past
  the next relcache reset unless `makecopy = true`. The comment is
  explicit. [from-comment §foreign.c:466-472]
- **`postgresql_fdw_validator` is documented deprecated.** Its
  conninfo list is hard-coded and won't track libpq additions. New
  FDWs should validate against libpq itself via `PQconninfoOptions`.
  postgres_fdw has its own validator. [from-comment §foreign.c:651-654]
- **`GetExistingLocalJoinPath` only handles unparameterized paths.**
  Comment: "Right now, this function only supports unparameterized
  foreign joins". A parameterized pushed-down join's EPQ falls
  through to NULL → planner errors out further up. [from-comment §foreign.c:755-757]

## Potential issues

- **File-line `foreign.c:607-624`.** The hard-coded
  `libpq_conninfo_options[]` is stale — it includes `tty` (removed
  from libpq long ago) and lacks many modern options (`channel_binding`,
  `target_session_attrs`, `keepalives_*`, `tcp_user_timeout`,
  `gssencmode`, `sslnegotiation`, …). The header comment marks the
  validator deprecated, but it's still callable from user SQL via
  `CREATE FOREIGN DATA WRAPPER ... VALIDATOR postgresql_fdw_validator`
  and that path will reject perfectly valid modern options.
  [ISSUE-doc-drift: libpq_conninfo_options stale vs current libpq (likely)]
- **File-line `foreign.c:497-499`.** When `makecopy` is true,
  `GetFdwRoutineForRelation` calls `palloc_object(FdwRoutine)` +
  `memcpy` in caller's CurrentMemoryContext. The Routine struct
  contains function pointers — no problem — but if a future FDW
  added a palloc'd subsidiary field, this `memcpy` would silently
  share the pointer between caller-context copy and the cached
  CacheMemoryContext copy. [ISSUE-undocumented-invariant: FdwRoutine must remain pointer-free for makecopy to be safe (nit)]
- **File-line `foreign.c:885-890`.** `GetExistingLocalJoinPath`
  returns NULL when no usable local path exists; callers (in
  postgres_fdw and extensions) typically `ereport(ERROR)` on NULL,
  but that error message is FDW-specific and hard to map back to
  "no unparameterized local path available". Worth a `errdetail`
  emitter inside the helper. [ISSUE-question: should this surface a structured "why" rather than NULL? (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `foreign`](../../../../issues/foreign.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/foreign.md](../../../../subsystems/foreign.md)
