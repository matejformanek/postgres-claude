# dblink.c

**Source pin:** `4b0bf0788b0` · **Path:** `source/contrib/dblink/dblink.c` (3272 LOC)

## One-line summary

THE cross-cluster query bridge: opens libpq connections to other PostgreSQL
clusters from inside a backend, exposes `dblink_connect / disconnect / open /
close / fetch / exec / send_query / get_result / cancel_query / get_notify`
as SQL-callable functions, manages a backend-local hash of named persistent
connections plus one unnamed default, and provides `dblink_fdw_validator`
plus the SCRAM-passthrough plumbing for connecting through a foreign-server
+ user-mapping definition.

## Public API / entry points

All `PG_FUNCTION_INFO_V1` SQL-callable; line numbers point to the macro and
function body. Each takes `text` arguments (no enforced typing of conninfo
beyond what libpq does).

| Function | Body | Notes |
|---|---|---|
| `dblink_connect` | `source/contrib/dblink/dblink.c:283-363` | 1- or 2-arg; named or unnamed; runs `dblink_connstr_check` + `dblink_security_check` |
| `dblink_disconnect` | `:368-398` | Closes named or unnamed |
| `dblink_open` (cursor) | `:403-491` | DECLAREs cursor; auto-BEGINs xact if IDLE |
| `dblink_close` | `:496-578` | CLOSEs cursor; auto-COMMITs when last cursor of auto-xact closes |
| `dblink_fetch` | `:583-672` | FETCH n FROM cur |
| `dblink_record` | `:677-682` → `dblink_record_internal(_, false)` | Synchronous query |
| `dblink_send_query` | `:684-707` | Async PQsendQuery, returns int |
| `dblink_get_result` | `:709-714` → `dblink_record_internal(_, true)` | Async result reaper |
| `dblink_exec` | `:1391-1485` | Non-SELECT, no rowset |
| `dblink_get_connections` | `:1279-1307` | Returns text[] of named conns |
| `dblink_is_busy` | `:1317-1328` | PQisBusy after PQconsumeInput |
| `dblink_cancel_query` | `:1341-1358` | libpqsrv_cancel with 30s deadline |
| `dblink_error_message` | `:1371-1386` | PQerrorMessage of named conn |
| `dblink_get_pkey` | `:1494-1598` | Lookup local rel's PK columns |
| `dblink_build_sql_insert/_delete/_update` | `:1620-1856` | Generate SQL from local tuple's PK |
| `dblink_current_query` | `:1864-1870` | Now just an alias to `current_query()` |
| `dblink_get_notify` | `:1882-1926` | Drains LISTEN notifications on a remote conn |
| `dblink_fdw_validator` | `:1935-2004` | CREATE SERVER/USER MAPPING validator |

No hooks installed. No GUCs. No shared memory. State is entirely
process-local: one `pconn` (unnamed) static pointer (`:144`) plus one
`remoteConnHash` HTAB in `TopMemoryContext` (`:145, :2552-2562`).

## Key invariants

1. **A `remoteConnHashEnt` with `rconn.conn == NULL` is a leftover from a
   failed create and MUST be ignored by lookups / silently replaced by
   creates** `[from-comment, :158-163]`. This is why
   `createNewConnection` errors only when `found && hentry->rconn.conn !=
   NULL` (`:2579-2582`) and why `getConnectionByName` returns NULL on
   `hentry->rconn.conn == NULL` (`:2546-2549`).
2. **Connection-cache key is `char[NAMEDATALEN]`, truncated by
   `truncate_identifier`** before lookup/insert/delete (`:2542, :2575,
   :2601`). Two different-looking names that share their first
   NAMEDATALEN−1 bytes collide. This is the NAME-vs-OID pattern: the
   foreign-server map keys on **OID** but the dblink named-conn map keys
   on a **truncated NAME string**.
3. **`pconn` (unnamed) lives in `TopMemoryContext` and survives across
   queries within the backend** (`:273`). On a connect-without-name, an
   existing `pconn->conn` is silently `libpqsrv_disconnect`ed and
   replaced (`:357-360`) — no warning.
4. **Cursor accounting on a named conn** uses `openCursorCount`. When
   `dblink_open` finds the conn in `PQTRANS_IDLE`, it BEGINs a xact, sets
   `newXactForCursor = true`, and forces `openCursorCount = 0` to recover
   from a stale state where an earlier ABORT killed the transaction
   without us knowing (`:459-474`). `dblink_close` decrements and COMMITs
   when count returns to zero (`:560-575`).
5. **`dblink_security_check` may longjmp out of `_connect`/`_record`
   midway**, but `libpqsrv_disconnect` has already been called inside the
   error branch (`:710-718`) — there's no PG_TRY around the body of
   `dblink_connect`, the connection is leaked into the hash entry on
   error path only via `deleteConnection(connname)` cleanup at
   `:711-712`.
6. **Synchronous `dblink_record_internal` uses `PG_TRY/PG_FINALLY` to
   guarantee `libpqsrv_disconnect(conn)` on the transient-conn path**
   when `freeconn == true` (`:819-825`). Async paths are different — the
   conn is named, so the caller is expected to dblink_disconnect.
7. **`materializeQueryResult` MUST drain libpq dry on PG_CATCH** —
   `:1085-1093` loops `libpqsrv_get_result` until NULL, otherwise the
   next call on this conn would see stale results.
8. **Tuple-descriptor width is checked against PQnfields BEFORE
   materializing** (`:925-929, :1213-1218`). Mismatch → ERROR
   `remote query result rowtype does not match the specified FROM clause
   rowtype`. Column **types** are NOT checked here — the cstring →
   in-function conversion at the local typmod is the implicit cast.
9. **GUC effects on conversion**: `applyRemoteGucs` (`:3145-3192`)
   creates a new GUC nestlevel and SET-LOCALs DateStyle + IntervalStyle
   from `PQparameterStatus` BEFORE running input functions over the
   remote tuple cstrings, then `restoreLocalGucs` (`:3197-3203`) pops.
   PG_TRY around the call sites ensures rollback on error via
   `AtEOXact_GUC` natively.

## Notable internals

### Connection cache

Hash `remoteConnHash` (HTAB, key = `char[NAMEDATALEN]`, value =
`remoteConnHashEnt { name, rconn }`, init size 16). Created lazily in
`createConnHash` (`:2552-2562`) using `HASH_ELEM | HASH_STRINGS`. There is
**no LRU, no max-conns cap, and no time-based eviction** — a session can
accumulate hundreds of persistent libpq sockets via repeated
`dblink_connect` calls under different names, bounded only by the
remote's `max_connections` and the local OS's per-process FD limit
[ISSUE-defense-in-depth: unbounded named-connection cache per backend
(maybe)]. `dblink_disconnect` removes from the hash; backend exit relies
on process teardown to clean up the sockets (TopMemoryContext destroyed,
libpq's own fds closed via OS).

### Role-as-cookie? No — invoker role IS the trust principal

The hash is keyed by user-supplied `name` only — there is no userid
component. Within a single backend, all connections in the cache are
"owned" by the session role; a `SET ROLE` to a different role inside the
session still sees the same hash, because there's no userid check at
lookup time. **However**, since the backend's `MyDatabaseId` and
`GetUserId()` are session-local and `dblink_security_check` runs on
EVERY connection establishment (`:2680-2719`), the per-call privilege
check still happens. The cache is just a libpq-handle reuse mechanism,
not a privilege store.

### Password-not-stored-on-connect-handle assertion

`dblink_security_check` (`:2681`) is the gatekeeper. Order:

1. `superuser()` → bypass all checks (`:2684-2685`).
2. Else: `PQconnectionUsedPassword(conn) && dblink_connstr_has_pw(connstr)`
   → OK. The libpq side reports whether the actual authentication
   exchange used a password; the local side parses the connstr to verify
   the user actually supplied one. If libpq grabbed a password from
   `~/.pgpass` / `PGPASSWORD` env / service file under the postmaster
   UID, `PQconnectionUsedPassword` is true but `dblink_connstr_has_pw` is
   false → REJECT.
3. Else: SCRAM passthrough — if the client connected to *us* with SCRAM
   and `MyProcPort->has_scram_keys` is set, and the connstr contains
   `require_auth=scram-sha-256` plus both `scram_client_key` and
   `scram_server_key`, those keys came from US (via
   `appendSCRAMKeysInfo`, `:3209-3241`) and the remote will SCRAM-auth
   using them. OK (`:2700-2701`).
4. Else (with `ENABLE_GSS`): if libpq used GSSAPI AND `MyProcPort` has
   delegated creds → OK (`:2703-2707`).
5. Else: `libpqsrv_disconnect`, `deleteConnection(connname)`, ereport
   `ERRCODE_S_R_E_PROHIBITED_SQL_STATEMENT_ATTEMPTED`,
   `"password or GSSAPI delegated credentials required"`
   (`:2710-2718`).

The pre-check `dblink_connstr_check` (`:2764-2785`) enforces the same
policy but BEFORE the libpq connect attempt — to forestall ever calling
libpq with no credentials, since libpq might consult `~/.pgpass` under
postmaster's UID.

### Async-query state machine

`dblink_send_query` → `PQsendQuery` returns int (1 ok / 0 err)
(`:684-707`). User then polls via `dblink_is_busy`. When ready,
`dblink_get_result` calls into `dblink_record_internal(fcinfo, true)`
which uses `libpqsrv_get_result` directly (NOT single-row mode — async
path uses old `materializeResult` accumulation, `:799-816`). Returning
NULL from `libpqsrv_get_result` signals "all done with this query's
results" `[from-comment, :802]`. Caller is responsible for keeping
polling until NULL.

### Connection-string sourcing via foreign server

`get_connect_string(name)` (`:2864-2955`):

1. `truncate_identifier(srvname, ...)` then `GetForeignServerByName` —
   note `missing_ok = true`, so a NULL return means "name is not a
   foreign server" and the caller (`dblink_get_conn`, `:215-217`) falls
   back to treating the string as a literal conninfo.
2. `GetUserMapping(GetUserId(), serverid)` — user mapping lookup. If
   none exists, this throws ERROR (GetUserMapping does so internally).
3. `object_aclcheck(ForeignServerRelationId, ..., ACL_USAGE)`
   (`:2911-2913`) — enforces GRANT USAGE on the foreign server.
4. If `MyProcPort->has_scram_keys` AND `UseScramPassthrough(...)`,
   prepend `scram_client_key=… scram_server_key=… require_auth=…` to
   the constructed connstr (`:2920-2921`).
5. Append FDW options, then server options, then user-mapping options —
   each filtered through `is_valid_dblink_option` (`:3066-3112`) which
   gates `user` and `*`-marked-secure options to UserMappingRelationId
   context and everything else to ForeignServerRelationId context.
6. Disallows `client_encoding` (`:3086`) — would be overridden anyway.
7. Disallows OAuth options (`:3093-3094`) — "builtin flow communicates
   on stderr by default and can't cache tokens yet".
8. Disallows libpq debug options via `strchr(opt->dispchar, 'D')`
   (`:3082-3083`) — most notably `replication`.

### Tuple-descriptor mismatch behavior

`materializeResult` and `storeRow` both call
`get_call_result_type(fcinfo, NULL, &tupdesc)` — they expect the SQL
caller to have specified `AS (col1 type1, col2 type2, ...)` or to be
returning a registered composite type. **Column count** is checked
strictly (`:925-929, :1213-1218`). **Column types** are NOT checked
ahead of time — `BuildTupleFromCStrings` invokes the typmod's input
function on the remote's text representation; mismatched types will
throw the input-function's own error (e.g. `invalid input syntax for
type integer: "hello"`) per-row.

## Trust boundary / Phase D surface

### The conninfo-trust model (the THE issue)

dblink does NOT validate that the conninfo points to a "safe" host. It
will happily open a libpq connection to `host=127.0.0.1 port=5432
dbname=postgres user=postgres` if the invoker role can satisfy the
authentication challenge AT THE LOCAL HOST. The only credential checks
are `dblink_connstr_check` + `dblink_security_check`.

**Loopback dblink as RLS bypass / privilege escalation**:

- A non-superuser `alice` with `pg_read_all_data` revoked from her on
  table `secrets` (RLS in effect) writes a connstr to localhost as
  herself, providing her password explicitly:
  `SELECT dblink_exec('host=/tmp port=5432 user=alice
  password=hunter2 dbname=app', 'SET row_security=off')` — would
  succeed in dropping RLS for the remote session because
  `row_security=off` is a USERSET GUC. Then she runs `dblink_record('SELECT
  * FROM secrets')` and obtains the full table. This IS the
  documented intended behavior — RLS is bypassable by a superuser, and
  `row_security=off` is bypassable by table owners. But the lateral move
  via dblink ALSO allows alice to bypass `pg_hba.conf` restrictions IF
  her remote auth method is local trust
  [ISSUE-security: loopback dblink bypasses pg_hba host-based
  restrictions when local auth is trust/peer (likely)] — the
  classic CVE-2018-1058–shaped class of issue, well known in PG circles.

- A non-superuser whose `postgres` OS user can read `~/.pgpass`: they
  CANNOT exploit that file because `dblink_connstr_check`
  (`:2764-2785`) requires the password literally in the connstr. Good.

- Superuser bypasses `dblink_security_check` entirely (`:2684`). For
  superuser ⇒ remote-superuser, the remote `pg_hba.conf` is the only
  defense. This is the documented and unavoidable trust model.

### Password handling in error messages

`dblink_connect` (`:332-340`) calls `pchomp(PQerrorMessage(conn))` and
ereport-errdetails it. libpq's error messages typically don't echo
the password, but DO echo the connstr in some failure modes (e.g.
`connection to server at "host" failed: ...`). `errdetail_internal`
prevents translation but the message still flows to the client. The
connstr itself was constructed locally — it doesn't contain anything
the caller didn't already supply — so no NEW leak, but the error
message is unsuppressed
[ISSUE-error-handling: PQerrorMessage forwarded verbatim via
errdetail_internal could leak environment-derived defaults if
`libpq` enriches the connstr (nit)] — looks low.

### `dblink_get_connections()` info leak

`:1279-1307` lists all named connections in the cache as a `text[]`.
There's no ACL on this function (typical GRANT EXECUTE to PUBLIC via
the install SQL — see `dblink--1.2.sql`). Within a single backend the
list is session-local, but a multi-tenant deployment where multiple
roles share a connection-pooler-bound backend session would see each
other's connection names. The names are arbitrary user strings, but
could embed hostnames, role names, or environment hints by convention
[ISSUE-audit-gap: dblink_get_connections has no ACL gate; named
connections from a previous SET ROLE are visible to subsequent SET
ROLEs in the same backend (nit)].

### NAME-vs-OID pattern in `dblink_get_pkey` and friends

`get_rel_from_relname` (`:2495-2506`) calls
`makeRangeVarFromNameList(textToQualifiedNameList(relname_text))` →
`RangeVarGetRelidExtended` with a callback `RangeVarCallbackForDblink`
(`:2477-2488`) that does `pg_class_aclcheck(relId, GetUserId(),
*aclmode)`. So dblink resolves relation names through the SAME path as
the parser uses (`search_path` honoured), and re-checks SELECT acl on
the OID returned. This is correct. The NAME lookup is `search_path`-
dependent so an attacker could shadow a target table by creating a
same-named one earlier in `search_path` — but the callback re-acls so
the shadow attack succeeds only against tables the user already has
SELECT on, limiting damage.

### Async cancellation discipline

`dblink_cancel_query` (`:1341-1358`) uses `libpqsrv_cancel` with a
30 000 ms deadline. Hard-coded — no GUC to adjust
[ISSUE-api-shape: 30s cancel deadline hardcoded (nit)]. Returns "OK"
or the libpq error text.

### Server-name-vs-conninfo (NAME-vs-OID for foreign servers)

`get_connect_string` (`:2864`) handles the foreign-server-by-name path.
**The crucial subtle bit**: at `:2899`,
`GetForeignServerByName(srvname, true /* missing_ok */)` returns NULL
if `srvname` is not a foreign server name, and the caller falls back to
treating it as a raw libpq connstr (`dblink_get_conn`, `:215-217`).
So an invoker with `USAGE` on a foreign server `prod_db` (good) can
also pass a literal connstr `"host=evil.attacker.com ..."`
(`dblink_connstr_check` permitting). The FDW abstraction is NOT a
sandbox — it's just sugar over hand-written connstrs.

### Connection-cache eviction policy

None. See "Connection cache" above. A backend that does
`dblink_connect('c1', ...); dblink_connect('c2', ...); ...; dblink_disconnect('cN')`
for the only one it explicitly tears down can hold N-1 idle libpq
sockets until backend exit.

### Tuple-descriptor mismatch — type confusion

The local function declares the tupdesc as e.g. `AS (a int, b text)`.
If the remote returns `(text, text)` for those columns, the local
input function for `int` is called on the remote's text bytes and
produces either a valid int or a normal SQL error. There's no buffer
overflow surface — the cstring is libpq-NUL-terminated. But: input
functions ARE permitted to allocate large amounts of memory based on
input length (e.g. arrays, jsonb), so a malicious remote can OOM the
LOCAL backend by returning a 1 GB cstring that the local input fn
explodes into 4 GB during parsing
[ISSUE-defense-in-depth: no size cap on remote PQgetvalue results
before passing through input fn (maybe)] — this is the standard libpq
exposure shape and applies to any libpq-using extension.

### Per-tuple memory leak prevention

`storeRow` uses a `tmpcontext` it created at
`materializeQueryResult` time (`:1015-1018`) and resets between rows
(`:1271`). Good. But `materializeResult` (used by the cursor+async
paths) does NOT reset between rows — it relies on the caller's
short-lived context plus per-call cleanup. For very large fetches
through `dblink_fetch`, this could matter; the comment at
`:648-651` notes libpq uses malloc so the PGresult is long-lived even
in a short-lived memory context. Looks OK in practice.

### `dblink_fdw_validator` boolean-only check for `use_scram_passthrough`

`:1999-2000` calls `defGetBoolean(def)` purely for its side-effect of
erroring on non-boolean. The boolean is RECHECKED later in
`UseScramPassthrough` (`:3251-3272`) which iterates options again. Fine.

### `applyRemoteGucs` only handles `DateStyle, IntervalStyle`

`:3148-3151`. If the remote uses a non-default `extra_float_digits` or
a different `bytea_output` (`hex` vs `escape`), the local input
function may misparse. Not a security issue, just a correctness gap
[ISSUE-correctness: applyRemoteGucs covers only DateStyle +
IntervalStyle; extra_float_digits / bytea_output mismatches silently
mis-decode (maybe)].

### Async path doesn't apply remote GUCs

`dblink_record_internal` with `is_async = true` calls
`materializeResult(fcinfo, conn, res)` (`:813`) which calls
`applyRemoteGucs` (`:944`). Wait — it DOES. OK. But
`materializeResult` only applies remote GUCs once for the entire
result accumulated by libpq's default mode, which assumes the remote
sent one ParameterStatus block at the start of the session. If the
remote ran `SET DateStyle` mid-query (impossible without
super-explicit pg_settings_clear etc.), the value at this point is
the post-query one. OK in practice.

## Cross-references

- **A2 libpq** — `source/src/interfaces/libpq/fe-connect.c`,
  `fe-secure-common.c`, `fe-auth-scram.c`: dblink's
  `dblink_security_check` relies on `PQconnectionUsedPassword`,
  `PQconnectionUsedGSSAPI`, and `MyProcPort->has_scram_keys` /
  `scram_ClientKey` / `scram_ServerKey` — the SCRAM-passthrough
  protocol is rendered into a connstr here and parsed by libpq there.
- `source/src/backend/libpq/libpq-be-fe-helpers.h` —
  `libpqsrv_connect_start`, `libpqsrv_connect_complete`,
  `libpqsrv_exec`, `libpqsrv_get_result`, `libpqsrv_cancel`,
  `libpqsrv_disconnect`, `libpqsrv_notice_receiver`. These wrappers
  are what makes libpq calls interruptible by CHECK_FOR_INTERRUPTS
  while waiting on socket I/O.
- `source/src/backend/foreign/foreign.c` — `GetForeignServerByName`,
  `GetUserMapping`, `GetForeignDataWrapper`. dblink's
  `get_connect_string` uses these to assemble the connstr from
  catalog options.
- `source/src/backend/utils/adt/varlena.c` — `truncate_identifier`
  used at `:2542, :2575, :2601, :2898`.
- `source/src/backend/access/common/tupdesc.c` —
  `BuildTupleFromCStrings`, `TupleDescGetAttInMetadata`.
- sibling contrib: `postgres_fdw` is the modern replacement —
  declarative FDW with column-type mapping, predicate pushdown, async
  remote estimates. dblink is the manual/explicit equivalent.

## Issues spotted

- [ISSUE-security: loopback dblink bypasses pg_hba host-based
  restrictions when local auth is trust/peer (likely)] — `:2864-2955`
  + `:283-363`; the conninfo-trust model accepts any host the OS can
  resolve, and `pg_hba` is the only check on the remote side. Classic
  vector for unintended privilege moves on a host where superuser is
  trust-authed locally.
- [ISSUE-defense-in-depth: unbounded named-connection cache per
  backend (maybe)] — `:2552-2588`; no max-conns ceiling, no LRU; a
  pooler-backed session can accumulate libpq sockets.
- [ISSUE-audit-gap: dblink_get_connections has no ACL gate (nit)] —
  `:1279-1307`; cross-SET ROLE leakage within a shared backend
  session.
- [ISSUE-defense-in-depth: no size cap on remote PQgetvalue results
  before passing through local input fn (maybe)] — `:1255-1267,
  :965-968`; a malicious remote can drive local backend OOM via large
  input-fn expansions.
- [ISSUE-correctness: applyRemoteGucs covers only DateStyle +
  IntervalStyle; other I/O-affecting GUCs silently differ (maybe)] —
  `:3148-3151`.
- [ISSUE-api-shape: 30s cancel deadline hardcoded in
  dblink_cancel_query (nit)] — `:1351-1352`.
- [ISSUE-error-handling: PQerrorMessage forwarded verbatim via
  errdetail_internal could leak hints about local environment if
  libpq enriches a partial connstr (nit)] — `:332-340, :238-239`.
- [ISSUE-concurrency: unnamed `pconn->conn` silently replaced when a
  second unnamed connect happens (nit)] — `:357-360`; no warning, the
  old conn is just disconnected.
- [ISSUE-api-shape: connection-cache key is NAMEDATALEN-truncated
  identifier (nit)] — `:2542 etc.`; two distinct-looking names that
  share their first NAMEDATALEN−1 bytes collide. NAME-vs-OID pattern.
- [ISSUE-audit-gap: superuser bypasses dblink_security_check entirely;
  no audit log of cross-cluster connection attempts (maybe)] —
  `:2684-2685`; combined with the conninfo-trust gap above, a
  compromised-superuser → other-cluster pivot is invisible to local
  auditing.
- [ISSUE-correctness: dblink_open auto-BEGINs xact on the remote when
  PQTRANS_IDLE, leaving openCursorCount=0 reset (nit)] — `:459-474`;
  the comment notes this recovers from a stale state after ABORT, but
  it means a long-lived session that hit a remote error mid-cursor
  silently loses cursor-count accounting; not a security issue.
- [ISSUE-memory: storeInfo.tmpcontext deleted only on PG_TRY success
  path; on PG_CATCH (`:1084-1093`) it's leaked into the parent
  context until that resets (nit)] — `:1077-1083` vs `:1084-1093`.
