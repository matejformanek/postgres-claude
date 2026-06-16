# `src/include/foreign/foreign.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~88
- **Source:** `source/src/include/foreign/foreign.h`

In-memory records for the foreign-data infrastructure — what gets
returned when you look up an FDW, a foreign server, a user mapping,
or a foreign table by OID or by name. Backing catalogs are
`pg_foreign_data_wrapper`, `pg_foreign_server`, `pg_user_mapping`,
`pg_foreign_table`. [verified-by-code]

## API / declarations

- `MappingUserName(userid)` macro — `OidIsValid(userid) ?
  GetUserNameFromId(userid, false) : "public"`. [verified-by-code]
- `ForeignDataWrapper { fdwid, owner, fdwname, fdwhandler,
  fdwvalidator, fdwconnection, options (List of DefElem) }` —
  `fdwconnection` (Oid of connection-string function) is a relatively
  recent addition (PG 17+) used by ALTER USER MAPPING and similar to
  generate effective connstrings without exposing passwords.
  [verified-by-code]
- `ForeignServer { serverid, fdwid, owner, servername, servertype
  (optional), serverversion (optional), options }`.
- `UserMapping { umid, userid, serverid, options }`.
- `ForeignTable { relid, serverid, options }`.
- Flag bits for the "extended" lookups:
  - `FSV_MISSING_OK 0x01` (Get*ServerExtended),
  - `FDW_MISSING_OK 0x01` (Get*DataWrapperExtended).
- Lookups:
  - `GetForeignServer(serverid)`,
    `GetForeignServerExtended(serverid, flags)`,
    `GetForeignServerByName(srvname, missing_ok)`,
  - `ForeignServerConnectionString(userid, server)`,
  - `GetUserMapping(userid, serverid)`,
  - `GetForeignDataWrapper(fdwid)`,
    `GetForeignDataWrapperExtended(fdwid, flags)`,
    `GetForeignDataWrapperByName(fdwname, missing_ok)`,
  - `GetForeignTable(relid)`,
  - `GetForeignColumnOptions(relid, attnum)`.
- OID resolution:
  - `get_foreign_data_wrapper_oid(fdwname, missing_ok)`,
  - `get_foreign_server_oid(servername, missing_ok)`.

## Notable invariants / details

- All four records embed their `options` as a `List *` of
  `DefElem` (untyped key/value) — the FDW is responsible for
  parsing/validating options on each access (see fdwvalidator).
  [inferred]
- The `Extended` lookups take a flag bitmask rather than a boolean
  so future "missing/skip-privilege-check/etc." additions stay
  binary-compatible. [inferred]
- `MappingUserName` falls back to literal `"public"` for invalid
  user OID — used by PUBLIC user mappings.

## Potential issues

- `ForeignServer.servertype` and `serverversion` are optional and
  the header does not say whether NULL is signaled by NULL pointer
  or empty string. (Looking at create_foreign_server.c: NULL
  pointer.) [ISSUE-doc-drift: NULL signaling for optional fields
  (nit)]
- `options` lists are owned by the cache copy; mutating them in
  place corrupts cached lookups for other backends. The header
  doesn't say "treat as const". [ISSUE-undocumented-invariant:
  options Lists should be treated as immutable (likely)]
- `GetForeignServer` (non-Extended) raises an `ereport(ERROR)` on
  missing — the header doesn't document the failure mode.
  [ISSUE-doc-drift: missing-OK vs error contract (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-foreign`](../../../../issues/include-foreign.md)
<!-- issues:auto:end -->
