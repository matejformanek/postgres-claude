# libpq-fe.h

- **Source path:** `source/src/interfaces/libpq/libpq-fe.h`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 878 lines

## Purpose

> "This file contains definitions for structures and externs for functions used by frontend postgres applications." [`libpq-fe.h:3-5`, from-comment]

**The** public libpq API contract. Every PQ* symbol exported by the libpq.so shared library has its prototype here. Stability promise (line 83-86): "Although it is okay to add to these lists, values which become unused should never be removed, nor should constants be redefined - that would break compatibility with existing code." [verified-by-code]

## Feature-detection macros (lines 36-70)

Compile-time symbols clients can `#ifdef` to detect libpq features by PG version:

- v14: `LIBPQ_HAS_PIPELINING`, `LIBPQ_HAS_TRACE_FLAGS`
- v15: `LIBPQ_HAS_SSL_LIBRARY_DETECTION`
- v17: `LIBPQ_HAS_ASYNC_CANCEL`, `LIBPQ_HAS_CHANGE_PASSWORD`, `LIBPQ_HAS_CHUNK_MODE`, `LIBPQ_HAS_CLOSE_PREPARED`, `LIBPQ_HAS_SEND_PIPELINE_SYNC`, `LIBPQ_HAS_SOCKET_POLL`
- v18: `LIBPQ_HAS_FULL_PROTOCOL_VERSION`, `LIBPQ_HAS_PROMPT_OAUTH_DEVICE`
- v19: `LIBPQ_HAS_GET_THREAD_LOCK`, `LIBPQ_HAS_OAUTH_BEARER_TOKEN_V2`

[verified-by-code at lines 38-70]

## Enums

- `ConnStatusType` (lines 88-117) — connection state machine. `CONNECTION_OK`, `CONNECTION_BAD`; below that are non-blocking-only internal states the comment says "should never be relied upon". `CONNECTION_SETENV` (line 104) is marked "This state is no longer used" but **the enumerator value is retained** to preserve ABI ordinals. [verified-by-code]
- `PostgresPollingStatusType` (lines 119-126) — `PGRES_POLLING_FAILED/READING/WRITING/OK`, plus `PGRES_POLLING_ACTIVE` marked "unused; keep for backwards compatibility". [verified-by-code]
- `ExecStatusType` (lines 128-149) — result status: `PGRES_EMPTY_QUERY`, `PGRES_COMMAND_OK`, `PGRES_TUPLES_OK`, `PGRES_COPY_OUT/IN/BOTH`, `PGRES_BAD_RESPONSE`, `PGRES_NONFATAL_ERROR`, `PGRES_FATAL_ERROR`, `PGRES_SINGLE_TUPLE`, `PGRES_PIPELINE_SYNC`, `PGRES_PIPELINE_ABORTED`, `PGRES_TUPLES_CHUNK`.
- `PGTransactionStatusType` (lines 151-158) — `PQTRANS_IDLE/ACTIVE/INTRANS/INERROR/UNKNOWN`.
- `PGVerbosity` (lines 160-166) — `PQERRORS_TERSE/DEFAULT/VERBOSE/SQLSTATE`.
- `PGContextVisibility` (lines 168-173) — `PQSHOW_CONTEXT_NEVER/ERRORS/ALWAYS`.
- `PGPing` (lines 180-186) — `PQPING_OK/REJECT/NO_RESPONSE/NO_ATTEMPT`. Comment notes: "values are exposed externally via pg_isready" — ordering is part of CLI contract. [verified-by-code]
- `PGpipelineStatus` (lines 191-196) — `PQ_PIPELINE_OFF/ON/ABORTED`.
- `PGauthData` (lines 198-205) — auth callback types. **Both** `PQAUTHDATA_OAUTH_BEARER_TOKEN` (v1) and `PQAUTHDATA_OAUTH_BEARER_TOKEN_V2` are exported; comment says v2 is preferred. [verified-by-code]

## Opaque struct typedefs

- `PGconn` ← `struct pg_conn` (line 211) — "contents not supposed to be known to applications"
- `PGcancelConn` ← `struct pg_cancel_conn` (line 217) — v17 async cancel
- `PGresult` ← `struct pg_result` (line 225)
- `PGcancel` ← `struct pg_cancel` (line 232) — legacy cancel
- `PGnotify` (lines 241-248) — **not opaque**, fields are exposed (`relname`, `be_pid`, `extra`) — comment: "Ideally this would be an opaque typedef, but it's so simple that it's unlikely to change." Trailing `next` field "private to libpq; apps should not use 'em".

## Public function categories

### Connection (fe-connect.c, lines 334-487)

Async start/poll: `PQconnectStart`, `PQconnectStartParams`, `PQconnectPoll`.
Sync: `PQconnectdb`, `PQconnectdbParams`, `PQsetdbLogin` (and the `PQsetdb` macro).
Teardown: `PQfinish`.
Option introspection: `PQconndefaults`, `PQconninfoParse`, `PQconninfo`, `PQconninfoFree`.
Reset: `PQresetStart`/`PQresetPoll`/`PQreset`.
Cancel (v17 async): `PQcancelCreate`, `PQcancelStart`, `PQcancelBlocking`, `PQcancelPoll`, `PQcancelStatus`, `PQcancelSocket`, `PQcancelErrorMessage`, `PQcancelReset`, `PQcancelFinish`.
Cancel (legacy): `PQgetCancel`/`PQfreeCancel`/`PQcancel` (signal-safe but deprecated), `PQrequestCancel` ("deprecated version of PQcancel; not thread-safe"). [verified-by-code at 405-409]
PGconn accessors: `PQdb`, `PQuser`, `PQpass`, `PQhost`, `PQhostaddr`, `PQport`, `PQtty`, `PQoptions`, `PQstatus`, `PQtransactionStatus`, `PQparameterStatus`, `PQprotocolVersion`, `PQfullProtocolVersion` (v18), `PQserverVersion`, `PQerrorMessage`, `PQsocket`, `PQbackendPID`, `PQpipelineStatus`, `PQconnectionNeedsPassword`, `PQconnectionUsedPassword`, `PQconnectionUsedGSSAPI`, `PQclientEncoding`, `PQsetClientEncoding`.
SSL info: `PQsslInUse`, `PQsslStruct`, `PQsslAttribute`, `PQsslAttributeNames`, `PQgetssl`, `PQinitSSL`, `PQinitOpenSSL`.
GSS info: `PQgssEncInUse`, `PQgetgssctx`.
Verbosity/visibility: `PQsetErrorVerbosity`, `PQsetErrorContextVisibility`.
Notice hooks: `PQsetNoticeReceiver`, `PQsetNoticeProcessor`.
Thread lock: `PQregisterThreadLock` (callback for non-thread-safe Kerberos/Curl coexistence), `PQgetThreadLock` (v19).

### Trace (fe-trace.c, lines 489-498)

`PQtrace(conn, FILE*)`, `PQuntrace`, `PQsetTraceFlags`. Flags: `PQTRACE_SUPPRESS_TIMESTAMPS`, `PQTRACE_REGRESS_MODE`.

### Exec (fe-exec.c, lines 500-676)

Sync exec: `PQexec`, `PQexecParams`, `PQprepare`, `PQexecPrepared`.
Async send: `PQsendQuery`, `PQsendQueryParams`, `PQsendPrepare`, `PQsendQueryPrepared`. Bound by `PQ_QUERY_PARAM_MAX_LIMIT` = 65535 (line 524). [verified-by-code]
Row modes: `PQsetSingleRowMode`, `PQsetChunkedRowsMode` (v17).
Async retrieve: `PQgetResult`, `PQisBusy`, `PQconsumeInput`.
Pipeline: `PQenterPipelineMode`, `PQexitPipelineMode`, `PQpipelineSync`, `PQsendFlushRequest`, `PQsendPipelineSync` (v17).
NOTIFY: `PQnotifies`.
COPY: `PQputCopyData`, `PQputCopyEnd`, `PQgetCopyData`.
Deprecated COPY: `PQgetline`, `PQputline`, `PQgetlineAsync`, `PQputnbytes`, `PQendcopy` (explicitly tagged "Deprecated routines" at line 568). [verified-by-code]
Non-block + ping: `PQsetnonblocking`, `PQisnonblocking`, `PQisthreadsafe`, `PQping`, `PQpingParams`, `PQflush`.
Fast path: `PQfn` — "not really recommended for application use" (line 587). [from-comment]
PGresult accessors: `PQresultStatus`, `PQresStatus`, `PQresultErrorMessage`, `PQresultVerboseErrorMessage`, `PQresultErrorField`, `PQntuples`, `PQnfields`, `PQbinaryTuples`, `PQfname`, `PQfnumber`, `PQftable`, `PQftablecol`, `PQfformat`, `PQftype`, `PQfsize`, `PQfmod`, `PQcmdStatus`, `PQoidStatus` ("old and ugly", line 618), `PQoidValue` ("new and improved"), `PQcmdTuples`, `PQgetvalue`, `PQgetlength`, `PQgetisnull`, `PQnparams`, `PQparamtype`.
Describe/Close (v17): `PQdescribePrepared/Portal`, `PQsendDescribePrepared/Portal`, `PQclosePrepared/Portal`, `PQsendClosePrepared/Portal`.
Result lifecycle: `PQclear`, `PQfreemem`. `PQfreeNotify(ptr)` is a back-compat macro alias for `PQfreemem` (line 646).
Result builders: `PQmakeEmptyPGresult`, `PQcopyResult`, `PQsetResultAttrs`, `PQresultAlloc`, `PQresultMemorySize`, `PQsetvalue`. `PG_COPYRES_*` flag macros: `PG_COPYRES_ATTRS` 0x01, `PG_COPYRES_TUPLES` 0x02, `PG_COPYRES_EVENTS` 0x04, `PG_COPYRES_NOTICEHOOKS` 0x08.
Quoting: `PQescapeStringConn`, `PQescapeLiteral`, `PQescapeIdentifier`, `PQescapeByteaConn`, `PQunescapeBytea`. **Deprecated** (no-conn variants do not know server's `standard_conforming_strings`): `PQescapeString`, `PQescapeBytea` (line 672-675). [verified-by-code]

### Print (fe-print.c, lines 679-700)

`PQprint` and the **really old** `PQdisplayTuples`/`PQprintTuples` (comment: "really old printing routines", line 686). All three are essentially deprecated relics from pre-psql days. [from-comment]

### Large objects (fe-lobj.c, lines 703-721)

`lo_open`, `lo_close`, `lo_read`, `lo_write`, `lo_lseek`, `lo_lseek64`, `lo_creat`, `lo_create`, `lo_tell`, `lo_tell64`, `lo_truncate`, `lo_truncate64`, `lo_unlink`, `lo_import`, `lo_import_with_oid`, `lo_export`. Naming convention: `lo_*` (lowercase) for LO routines, **not** `PQ*`.

### Misc (fe-misc.c, lines 723-745)

`PQlibVersion`, `PQsocketPoll`, `PQgetCurrentTimeUSec` (v17), `PQmblen`, `PQmblenBounded`, `PQdsplen`, `PQenv2encoding`.

### Auth (fe-auth.c, lines 747-857)

OAuth device-flow callback struct `PGpromptOAuthDevice` (lines 750-757) carries verification URI, user code, optional combined URI, and `expires_in`.

`PGoauthBearerRequest` (lines 771-826) — v1 OAuth bearer-token callback. Fields:
- `openid_configuration`, `scope` (inputs)
- `async(conn, request, altsock)` callback returning `PostgresPollingStatusType`
- `cleanup(conn, request)` — must free `token` (and in V2, `error`); comment warns "no other indication as to when it is safe to free the token"
- `token` — Bearer token; must stay live until `cleanup` fires
- `user` — hook-defined opaque state

`PGoauthBearerRequestV2` (lines 831-848) — wraps v1, adds `issuer` (RFC 9207 input) and `error` (output message). Comment: "libpq does not take ownership of this pointer; any allocations should be freed during the cleanup callback." [verified-by-code]

Password / hooks: `PQencryptPassword` (deprecated; no algorithm parameter), `PQencryptPasswordConn`, `PQchangePassword` (v17).
Auth-data hook: `PQauthDataHook_type` typedef, `PQsetAuthDataHook`, `PQgetAuthDataHook`, `PQdefaultAuthDataHook`.

`PQ_SOCKTYPE` macro (lines 764-768) — `uintptr_t` on Windows, `int` elsewhere; `#undef`'d at line 828 so it doesn't leak into client namespace. **Trick to avoid forcing winsock2.h into client compile.** [verified-by-code]

### Encoding names (encnames.c, lines 859-863)

`pg_char_to_encoding`, `pg_encoding_to_char`, `pg_valid_server_encoding_id`. Note `pg_*` snake_case, not `PQ*`.

### SSL key-pass hook (fe-secure-openssl.c, lines 865-871)

`PQsslKeyPassHook_OpenSSL_type` typedef, `PQgetSSLKeyPassHook_OpenSSL`, `PQsetSSLKeyPassHook_OpenSSL`, `PQdefaultSSLKeyPassHook_OpenSSL`.

## Deprecated / legacy surface (Phase D candidates)

Symbols still exported despite being marked deprecated in comments — removing any of these is an ABI break:

- `PQsetdb` macro (line 352) — exists for back-compat with `PQsetdbLogin` even older callers.
- `PQrequestCancel` (line 409) — "not thread-safe".
- `PQcancel(cancel, errbuf, size)` (line 406) — old signal-safe cancel; superseded by `PQcancelBlocking`/`PQcancelStart`.
- `PQnoPasswordSupplied` string literal macro (line 650) — "depending on this is deprecated; use PQconnectionNeedsPassword()."
- `PQfreeNotify` macro (line 646) — back-compat alias.
- `PQgetline`/`PQputline`/`PQgetlineAsync`/`PQputnbytes`/`PQendcopy` (lines 568-573) — "Deprecated routines for copy in/out".
- `PQescapeString`/`PQescapeBytea` (lines 672-675) — no-conn variants miss `standard_conforming_strings`.
- `PQoidStatus` (line 618) — "old and ugly".
- `PQdisplayTuples`/`PQprintTuples` (lines 688-700) — "really old printing routines".
- `PQfn` (line 590) — "not really recommended".
- `PQAUTHDATA_OAUTH_BEARER_TOKEN` v1 — v2 is preferred but v1 stays exported.
- `PQinitSSL` — superseded by `PQinitOpenSSL`.
- `CONNECTION_SETENV` enumerator (line 104) — "no longer used" but value retained.
- `PGRES_POLLING_ACTIVE` (line 125) — "unused; keep for backwards compatibility".
- `PQprintOpt.standard`, `.html3` — `pqbool` fields from the 1990s `PQprint` era.

[ISSUE-libpq-fe-001 — maybe] No central deprecation policy doc in-tree. A client survey of which deprecated entry points are still called in the wild (especially `PQrequestCancel`, `PQescapeString`, `PQgetline`) would tell us what's safe to retire.

[ISSUE-libpq-fe-002 — maybe] `PQ_QUERY_PARAM_MAX_LIMIT` is 65535 (uint16 wire limit). Clients sending >65535 params get a runtime error in the send routines; no compile-time check. Could be lifted to a typed constant for static-assert by clients.

## Tally

`[verified-by-code]=10 [from-comment]=8 [maybe]=2`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new libpq protocol message](../../../../scenarios/add-new-protocol-message.md)

<!-- scenarios:auto:end -->
