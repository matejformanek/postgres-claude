# `src/backend/replication/libpqwalreceiver/libpqwalreceiver.c`

- **Last verified commit:** `a75bd485b5ea` (re-verified 2026-06-17; the
  replication-command quoting rewrite landed here — see "Replication-command
  quoting" below. Early-function cites unchanged; `libpqrcv_startstreaming`/
  `_endstreaming`/`_receive` and the disconnect path shifted +20/+27 lines.)
- **Lines:** ~1250 (file is ~37 KB)
- **Source:** `source/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c`

libpq-backed implementation of the abstract `WalReceiverFunctions`
table. Loaded as a dynamic module (`shared_preload_libraries`
needn't be set; it's dlopened on first need) so the main server
binary doesn't link libpq. Apart from physical walreceiver, it's
now also used by logical replication workers and slot
synchronization. [from-comment]

## Architecture

- `_PG_init()` (line 124) registers `PQWalReceiverFunctions` as
  the global `WalReceiverFunctions` pointer. Idempotency guard:
  `elog(ERROR, "libpqwalreceiver already loaded")` if called
  twice. [verified-by-code]
- `struct WalReceiverConn` — `{ PGconn *streamConn, bool logical,
  char *recvBuf }`. [verified-by-code]

## Connection setup (`libpqrcv_connect`)

`libpqrcv_connect(conninfo, replication, logical, must_use_password,
appname, *err)` (line 147):

1. Re-runs `libpqrcv_check_conninfo(conninfo, must_use_password)`
   even though DDL did so already — protects against subscription
   owner changes that could pick up `PGPASSFILE`/`PGPASSWORD` from
   a different source (line 157-164). [from-comment]
2. Builds a key/value array of libpq params using
   `expand_dbname=true`:
   - `dbname = conninfo` (the parser will expand URIs/keywords).
   - For replication: `replication=database` (logical) or `=true`
     (physical).
   - For logical: `client_encoding=<current DB encoding>` and
     `options="-c datestyle=ISO -c intervalstyle=postgres -c
     extra_float_digits=3"` — explicitly matches `pg_dump`
     output discipline so publisher row values are unambiguous on
     the subscriber. Existing `options` are concatenated.
     [verified-by-code]
   - For physical: dummy `dbname=replication` so `.pgpass` lookup
     keys correctly (server ignores dbname in physical mode).
3. `libpqsrv_connect_params_start` + `_connect_complete` (async
   connect, then wait on `WAIT_EVENT_LIBPQWALRECEIVER_CONNECT`).
4. `must_use_password` enforcement: post-connect, if
   `!PQconnectionUsedPassword`, ereport `ERRCODE_S_R_E_PROHIBITED
   _SQL_STATEMENT_ATTEMPTED` with the canonical errhint about
   `password_required=false` (line 244-249). This is the
   subscription-owner-without-superuser guard.
   [verified-by-code]
5. For SQL-running connections (logical or non-replication), runs
   `ALWAYS_SECURE_SEARCH_PATH_SQL` ("SELECT pg_catalog.set_config(
   'search_path', '', false)") so subsequent queries can't be
   shadowed by an attacker-controlled `public` schema (line 256-269).
   [verified-by-code]

## Connection-string validation (`libpqrcv_check_conninfo`)

Line 295. Parses with `PQconninfoParse`. When
`must_use_password=true`, scans the parsed options for a non-empty
`password` field and ereports with errcode
`ERRCODE_S_R_E_PROHIBITED_SQL_STATEMENT_ATTEMPTED` if missing.
[verified-by-code]

## Conninfo obfuscation (`libpqrcv_get_conninfo`)

Line 350. Walks `PQconninfo` keywords; any option whose
`dispchar` contains `'*'` (libpq's "secret" flag) is rendered as
`********` rather than its literal value. Skips debug (`'D'`)
options and empty values. [verified-by-code]

## Streaming protocol

- `libpqrcv_identify_system(conn, *primary_tli)` (line 423) —
  sends `IDENTIFY_SYSTEM`, validates `nfields >= 3 && ntuples == 1`,
  returns the system_id string and timeline. [verified-by-code]
- `libpqrcv_startstreaming(conn, opts)` (line 562) — builds
  `START_REPLICATION SLOT "name" LOGICAL X/Y (proto_version 'N',
  streaming 'X', two_phase 'on', origin 'X', publication_names
  'pubs', binary 'true')` or the physical equivalent with
  `TIMELINE n`. Version gates: `two_phase` >= PG15, `origin` >=
  PG16, `binary` >= PG14. Returns true if the server entered
  `PGRES_COPY_BOTH`, false on bare `PGRES_COMMAND_OK` (server
  switched to another timeline at/before our start LSN).
  [verified-by-code]
- `libpqrcv_endstreaming(conn, *next_tli)` (line 658) — graceful
  COPY shutdown; reads the trailing `PGRES_TUPLES_OK` to get the
  next-TLI value, or handles the abort-in-mid-copy case.
  [verified-by-code]
- `libpqrcv_receive(conn, **buffer, *wait_fd)` (line 803) — try
  `PQgetCopyData` async; on rawlen==0 do one `PQconsumeInput` +
  retry; if still empty, return 0 and surface `PQsocket` to the
  caller. -1 on end-of-stream. [verified-by-code]

## Replication-command quoting (`appendQuotedString`, since `a75bd485b5ea`)

The command builders no longer interpolate identifiers/literals with bare
`appendStringInfo(&cmd, " SLOT \"%s\"", slotname)`. A self-contained helper
`appendQuotedString(buf, str, quote)` (line 534) wraps the value in `quote`
and doubles any embedded `quote` char; two macros sit on top:
`appendQuotedIdentifier` (`'"'`) and `appendQuotedLiteral` (`'\''`) (lines
548-549). `libpqrcv_startstreaming` (slot name, line 578) and
`libpqrcv_create_slot` (slot name, lines 922/1029) now route through these.
The header comment cautions the logic is sufficient for the replication
grammar **but not regular SQL** — a literal would be mis-quoted if
`standard_conforming_strings` is off. [verified-by-code, libpqwalreceiver.c:526-549 @ a75bd485b5ea]

This also changed a signature: `stringlist_to_identifierstr` dropped its
leading `PGconn *conn` parameter (it used to need the conn for
`PQescapeStringConn`; now it uses the internal `appendQuotedIdentifier`).
Old: `stringlist_to_identifierstr(PGconn *conn, List *strings)`; new:
`stringlist_to_identifierstr(List *strings)` (definition line 1230, call
site line 618). Any out-of-tree caller of this static would not be
affected (it's file-local), but the mirror helper in
`subscriptioncmds.c` / `pg_basebackup` made the same change. [verified-by-code, libpqwalreceiver.c:119,618,1230 @ a75bd485b5ea]

## Replication-slot management

- `libpqrcv_create_slot(...)` — `CREATE_REPLICATION_SLOT` with
  modifiers `TEMPORARY`, `TWO_PHASE`, `FAILOVER`, and a
  `CRSSnapshotAction` (USE_SNAPSHOT / NOEXPORT_SNAPSHOT /
  EXPORT_SNAPSHOT). [from-prototype]
- `libpqrcv_alter_slot(conn, slotname, *failover, *two_phase)` —
  `ALTER_REPLICATION_SLOT` for failover-slot toggles (PG17+).
  [from-prototype]

## Notable invariants / details

- The conn struct's `recvBuf` is a malloc'd libpq buffer, NOT a
  palloc'd block; `PQfreemem(conn->recvBuf)` is required, not
  `pfree`. Disconnect path at line 782 honours this.
  [verified-by-code]
- Wait events used: `LIBPQWALRECEIVER_CONNECT`,
  `LIBPQWALRECEIVER_RECEIVE`. Both feed `pg_stat_activity` so
  operators can spot stuck replication setup.
  [verified-by-code]
- Errors from libpq go through `pchomp(PQerrorMessage(conn))` —
  strip trailing newline before passing into `errmsg`.
  [verified-by-code]
- The "always secure search path" run via `set_config(...,
  false)` (transient) means each call site that depends on it
  must keep using the same connection; a reset_session would wipe
  it. [inferred]

## Potential issues

- Line 152-153 — fixed-size `const char *keys[6]; vals[6]`; the
  insert sequence is at most 5 entries plus a NULL sentinel, so
  the `Assert(i < lengthof(keys))` at line 222 holds, but adding
  one more keyword in the future would silently overflow if the
  array isn't grown. [ISSUE-style: hard-coded 6-element libpq
  param array (nit)]
- Line 256-269 — `ALWAYS_SECURE_SEARCH_PATH_SQL` runs only for
  non-replication or logical connections, not for physical
  replication. Physical doesn't run SQL through this conn so
  that's intentional, but a future feature that runs SQL on a
  physical conn would inherit the unsafe search path.
  [ISSUE-undocumented-invariant: search-path lockdown skipped for
  physical replication (maybe)]
- The `must_use_password` check at line 239 happens after
  CONNECT_OK, so a server that accepts auth without ever asking
  for a password (e.g. `trust`, certificate, peer) is still
  caught — but the error path runs *after* connection
  establishment, briefly exposing the conn to whatever the server
  decides to send on the socket. In practice harmless but worth
  noting if reviewing for cert-based replication contexts.
  [ISSUE-question: password-required check is post-connect; brief
  window before disconnect (nit)]
- Line 197-199 — the `options` value for logical replication uses
  string concatenation with `psprintf`; if the user-supplied
  `options` contains a literal `-c session_replication_role=replica`
  or similar, that GUC gets applied on the publisher side. PG's
  walsender validates GUC names, but the concatenation order
  (user-supplied first, then our overrides) means user values are
  overridden by the forced trio — this is the intended behaviour
  but not commented inline. [ISSUE-undocumented-invariant:
  override-after-user-options order is significant (nit)]
- Line 40-43 — `PG_MODULE_MAGIC_EXT(.name="libpqwalreceiver",
  .version=PG_VERSION)` — this is a PG18 magic macro. Older module
  loaders won't recognise it; binary compat with PG17 client
  tooling rebuilding against PG18 sources will need care.
  [ISSUE-question: PG_MODULE_MAGIC_EXT vs PG_MODULE_MAGIC binary
  compatibility (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `replication`](../../../../../issues/replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/replication.md](../../../../../subsystems/replication.md)
