# connection.c

## One-line summary

The libpq connection cache, transaction-state machine, and security check that lives at the very edge of every postgres_fdw cross-cluster operation: a per-backend hash table keyed solely on `UserMapping.umid`, registers `XactCallback`/`SubXactCallback`/two syscache invalidators, drives REPEATABLE-READ remote xacts with SAVEPOINT-per-subxact, and refuses to give a non-superuser a connection that didn't actually authenticate with a password or delegated GSSAPI / SCRAM keys.

## Public API / entry points

SQL-callable:
- `postgres_fdw_get_connections() / postgres_fdw_get_connections_1_2()` (lines 2517, 2509) — set-returning, lists active connections. v1.1 returns `(server_name, valid)`. v1.2 adds `(user_name, used_in_xact, closed, remote_backend_pid)`. [verified-by-code at line 2276-2306]
- `postgres_fdw_disconnect(text servername)` (line 2537) — disconnect cached conns for one server. Returns true if at least one closed.
- `postgres_fdw_disconnect_all()` (line 2558) — disconnect all.
- `postgres_fdw_connection(userid, serverid) → text` (line 2469) — returns the resolved libpq connection string (with values single-quote-escaped via `appendEscapedValue` at line 2457).

C-callable (referenced from postgres_fdw.h):
- `GetConnection(UserMapping *user, bool will_prep_stmt, PgFdwConnState **state)` (line 216) — the cache lookup + auto-reconnect-on-stale-conn entry point.
- `ReleaseConnection(conn)` (line 1020) — **no-op**. Cleanup is xact-callback-driven, not refcount-driven (lines 1023-1027 comment). [verified-by-code]
- `GetCursorNumber`, `GetPrepStmtNumber` (lines 1042, 1056) — monotonic unsigned-int counters; `cursor_number` resets per top-xact (line 1316), prep-stmt never resets (line 1052 comment).
- `do_sql_command`, `do_sql_command_begin`/`_end`, `pgfdw_exec_query`, `pgfdw_get_result` (lines 849, 855, 862, 1071, 1088).
- `pgfdw_report_error` (line 1112, `pg_noreturn`) / `pgfdw_report` (line 1118).

Internal:
- `make_new_connection`, `connect_pg_server`, `disconnect_pg_server` (lines 378, 628, 689).
- `pgfdw_security_check` (line 446) — post-connect non-superuser password/GSSAPI/SCRAM check.
- `check_conn_params` (line 759) — pre-connect non-superuser password/GSSAPI/SCRAM check.
- `UserMappingPasswordRequired` (line 705), `UseScramPassthrough` (line 727).
- `construct_connection_params` (line 494) — builds the libpq `(keywords[], values[])` from ForeignServer + UserMapping + SCRAM keys + `fallback_application_name=postgres_fdw` + `client_encoding=<local>`.
- `configure_remote_session` (line 811) — issues `SET search_path = pg_catalog`, `SET timezone = 'GMT'`, `SET datestyle = ISO`, `SET intervalstyle = postgres`, `SET extra_float_digits = 3` on every new connection.
- `begin_remote_xact` (line 896) — opens `START TRANSACTION ISOLATION LEVEL REPEATABLE READ` (or SERIALIZABLE) with optional `READ ONLY`, `DEFERRABLE`; stacks `SAVEPOINT s%d` to match nesting.
- `pgfdw_xact_callback` / `pgfdw_subxact_callback` (lines 1173, 1326) — drive remote commit / abort / parallel-commit / parallel-abort.
- `pgfdw_cancel_query[_begin/_end]`, `pgfdw_exec_cleanup_query[_begin/_end]`, `pgfdw_get_cleanup_result` (lines 1571, 1604, 1617, 1671, 1691, 1709, 1769) — abort-cleanup state machine with `CONNECTION_CLEANUP_TIMEOUT=30000ms` and `RETRY_CANCEL_TIMEOUT=1000ms` (lines 106, 113).
- `pgfdw_abort_cleanup[_begin]`, `pgfdw_finish_pre_commit_cleanup`, `pgfdw_finish_pre_subcommit_cleanup`, `pgfdw_finish_abort_cleanup` (lines 1873, 1947, 2005, 2079, 2113).
- `pgfdw_inval_callback` (line 1442) — `FOREIGNSERVEROID` + `USERMAPPINGOID` syscache callbacks.
- `pgfdw_reject_incomplete_xact_state_change` (line 1497) — refuses to reuse a connection whose abort cleanup previously failed.
- `pgfdw_conn_check[able]` (lines 2658, 2695) — uses `poll(POLLRDHUP)` on Linux to detect dead remote.
- `pgfdw_has_required_scram_options` (line 2713) — for SCRAM pass-through.

## Key invariants

- INV-CACHE-KEY-UMID: cache key is `ConnCacheKey = Oid` set to `user->umid` (lines 54, 255). Comment at lines 41-45 explains: keying by umid rather than `(serverid, userid)` collapses the "public user mapping" case (one mapping serves all roles → one shared conn) **vs** keying by `(serverid, userid)` (which would give every role its own conn). The implication is in the Trust Boundary section below. [verified-by-code]
- INV-XACT-DEPTH-MIRRORS-LOCAL: `entry->xact_depth` must equal the local `GetCurrentTransactionNestLevel()` while the cache entry has a live remote xact. `begin_remote_xact` stacks SAVEPOINTs to catch up (lines 996-1014); `pgfdw_subxact_callback` releases on commit_sub / rolls back on abort_sub. The two CALLBACK functions are registered exactly once per backend (lines 243-244).
- INV-REPEATABLE-READ-MIN: every remote xact is started at least at REPEATABLE READ (lines 884-889 comment, line 938). If local is SERIALIZABLE, remote matches; otherwise REPEATABLE READ. **This is so that two SELECTs in the same local query see a snapshot-consistent view of the remote**. The corollary: local READ COMMITTED behavior cannot be emulated remotely. [from-comment]
- INV-CHANGING-XACT-STATE-POISON: if `entry->changing_xact_state` is true on entry to `GetConnection`, the connection is poisoned and `pgfdw_reject_incomplete_xact_state_change` throws `ERRCODE_CONNECTION_EXCEPTION` "connection to server ... cannot be used due to abort cleanup failure" (line 1509). Reconnecting would change snapshot and lose writes already done, so we abort the top xact. [verified-by-code]
- INV-PREPARE-DISALLOWED: `XACT_EVENT_PRE_PREPARE` unconditionally errors with `cannot PREPARE a transaction that has operated on postgres_fdw foreign tables` (line 1260). 2PC is not implemented end-to-end. [verified-by-code]
- INV-NON-SUPERUSER-MUST-AUTHENTICATE: `check_conn_params` (pre-connect) AND `pgfdw_security_check` (post-connect) both raise `ERRCODE_S_R_E_PROHIBITED_SQL_STATEMENT_ATTEMPTED` "password or GSSAPI delegated credentials required" if a non-superuser would otherwise piggyback on the postgres-OS-user's `.pgpass` / service file / env / Kerberos ticket. **Both checks** — the pre-check at line 759 guards against connection-time leaks, the post-check at line 446 guards against the case where libpq tried-and-failed-and-fell-back. Bypass only via superuser-set `password_required=false`. [verified-by-code]
- INV-DEALLOCATE-ALL-ON-SUBXACT-ABORT: if any subxact aborted (`have_error=true`) AND prepared statements were created (`have_prep_stmt=true`), a `DEALLOCATE ALL` is issued at top-commit time (lines 1240-1247) to avoid leaking prepared statements on the remote. Errors in DEALLOCATE are ignored (line 1242 explicit). [verified-by-code]
- INV-PREP-STMT-NUMBER-NEVER-RESETS: comment at lines 1049-1054 says it must never reset to avoid name collision with possibly-leaked statements.

## Notable internals

### Connection-cache key choice (this is THE pivotal design decision)

The cache is keyed by `user->umid` alone — not `(serverid, userid)`. This means:
- A single user mapping (incl. the **PUBLIC** user mapping, which has one umid covering every role) → ONE shared cache entry.
- If role A and role B both inherit the PUBLIC mapping for server S, they SHARE one PGconn. **All queries from A and B inside the same local backend session run as the same remote-side identity.** That's correct for postgres_fdw's design — the remote identity is the one in the user mapping, not the local identity.
- BUT: a non-superuser local backend that already opened a connection cannot have that connection's PGconn handle reach a different local role within the same backend — different local roles run as different local processes anyway in PG's connection model.

### Async-execution interaction

`PgFdwConnState` (defined in `postgres_fdw.h`) embeds an `AsyncRequest *pendingAreq`. `GetConnection` calls `process_pending_request` at line 301 BEFORE `begin_remote_xact`, draining any in-flight async fetch. Without this, a second SQL command issued on the same conn while libpq is still waiting on a FETCH would corrupt the protocol state.

### Abort-cleanup state machine

`pgfdw_abort_cleanup` (line 1873) runs:
1. If `in_error_recursion_trouble()`, mark `changing_xact_state=true` (poison) and bail.
2. If `PQtransactionStatus == PQTRANS_ACTIVE`, issue cancel (`pgfdw_cancel_query` with 30s timeout, 1s recancel).
3. Build `ABORT TRANSACTION` (or `ROLLBACK TO SAVEPOINT s<n>; RELEASE SAVEPOINT s<n>`) via `CONSTRUCT_ABORT_COMMAND` (lines 116-125) — note `RELEASE` after `ROLLBACK TO` for subxact; this destroys the savepoint name.
4. Execute with 30s timeout.
5. If toplevel and prep stmts may be leaked, issue `DEALLOCATE ALL`.
6. Clear `pendingAreq` and unset `changing_xact_state`.

`pgfdw_abort_cleanup_begin` + `pgfdw_finish_abort_cleanup` (lines 1947, 2113) is the parallel-abort variant: issue cancels / aborts on every entry, then wait for all results. Tradeoff: faster aggregate abort across many foreign servers, more complex error-state bookkeeping.

### Parallel commit (`parallel_commit` server option)

`XACT_EVENT_PRE_COMMIT` branch (lines 1206-1248): if `parallel_commit=true`, `do_sql_command_begin` is called (PQsendQuery only, no get_result), the entry is queued, and `pgfdw_finish_pre_commit_cleanup` drains all COMMITs in parallel (line 2005). This is **NOT 2PC** — there's no prepare phase. If commit #3 of 10 fails after commits #1-2 succeeded remotely, those #1-2 stand; the local xact errors out and ROLLBACKs locally. **The remote and local can disagree on commit/abort.** That's documented in the postgres_fdw docs as an acknowledged limitation.

### `configure_remote_session` (line 811) — the SET commands

Sets, on every new connection:
- `search_path = pg_catalog` — deparse.c forces all non-builtin names to be schema-qualified, so search_path must not pick up anything else.
- `timezone = 'GMT'` — for predictable regression-test output and timezone-agnostic timestamptz transmission.
- `datestyle = ISO`, `intervalstyle = postgres` (PG 8.4+), `extra_float_digits = 3` (PG 9.0+ — value 2 on older).

Comment at lines 802-809 acknowledges these can be subverted by a malicious view definition on the remote that includes a `set_config` call. "But once you admit the possibility of a malicious view definition, there are any number of ways to break things." — admission that the FDW does not defend against an actively malicious remote.

### `pgfdw_report_internal` (line 1126) — error translation

Translates a `PGresult` PG_DIAG_* fields into local ereport:
- SQLSTATE → `errcode(sqlstate)`, fallback `ERRCODE_CONNECTION_FAILURE`.
- PG_DIAG_MESSAGE_PRIMARY → `errmsg_internal` (translated as-is, NOT marked for internationalization).
- DETAIL → `errdetail_internal`, HINT → `errhint`, CONTEXT → `errcontext`.
- Plus `errcontext("remote SQL command: %s", sql)` if `sql` was passed (line 1161).

Implication: **the remote's error message text is echoed verbatim into local logs and to the client**. If the remote returns errors containing user-data fragments (column values, etc.), they appear locally.

### Connection-status check (`pgfdw_conn_check`, line 2658)

Uses `poll(POLLRDHUP)` — Linux-only (compile-time `#if defined(HAVE_POLL) && defined(POLLRDHUP)`). On other platforms, always returns 0 / "not checkable". `postgres_fdw_get_connections_1_2(check_connection=>true)` exposes this.

## Trust boundary / Phase D surface — THE FILE

### `password_required` enforcement chain (CVE-2023-5869 era)

**Two enforcement points (deliberately belt-and-suspenders):**

1. `check_conn_params` (line 759) — **pre-connect**. Walks the resolved keyword/value array; if non-superuser AND no `password=...` AND no GSS delegation AND no SCRAM passthrough AND `UserMappingPasswordRequired()`, ERROR. Prevents handing a connection string containing `password=` from `.pgpass` (which libpq could read on behalf of the postgres OS user) to a non-superuser.

2. `pgfdw_security_check` (line 446) — **post-connect**, called from `connect_pg_server` (line 666) after `libpqsrv_connect_complete`. Cross-checks `PQconnectionUsedPassword(conn)` — i.e. libpq confirms a password was actually sent on the wire. Defends against the case where the connection succeeded via a method that bypassed the keyword scan (e.g. `peer` auth on Unix sockets where libpq sent no password but the remote authenticated via OS UID).

**The check passes (i.e. non-superuser is allowed) iff ANY of:**
- The local role IS superuser.
- `UserMapping.password_required = false` (superuser-set on the mapping).
- A non-empty `password=...` was provided in the user mapping options AND `PQconnectionUsedPassword(conn)` returns true.
- GSSAPI was used AND `be_gssapi_get_delegation(MyProcPort)` confirms the local backend got delegated creds (line 454, `#ifdef ENABLE_GSS`).
- SCRAM pass-through: `MyProcPort->has_scram_keys` true AND `pgfdw_has_required_scram_options(keywords, values)` (line 2713) confirms `scram_client_key`, `scram_server_key` are set AND `require_auth=scram-sha-256` is set.

### Loopback-to-bypass-RLS / loopback-to-bypass-pg_hba (the canonical attack)

If a SERVER has `host=localhost port=5432` and a USER MAPPING has `password_required=false` (set by superuser):
- A non-superuser local user with USAGE on the SERVER and the mapping can issue `SELECT * FROM ft` and **postgres_fdw will open a loopback PGconn**.
- pg_hba.conf with `local trust` or `host 127.0.0.1 trust` or `peer` would treat this connection as the postgres OS user (often superuser equivalent).
- The remote backend then runs as whatever role the user mapping says (`user=`) — could be the superuser.
- **RLS is then bypassed** on the remote because the connection authenticated as a privileged role.

The defense is `password_required=true` (default) — the validator + the two security checks together force any non-superuser-initiated connection to authenticate explicitly. **A misconfigured `pg_hba.conf` + a `password_required=false` USER MAPPING is the documented attack pattern.**

### Connection reuse across user mappings — NOT POSSIBLE

Because the cache is keyed by umid, role A's PGconn is in cache slot `umid_A`, role B's is in `umid_B`. They cannot collide. However, **if both A and B inherit the PUBLIC user mapping** (a single umid), they SHARE the conn. That's correct: the remote identity is fixed by the mapping, so sharing is safe.

But: **`postgres_fdw_disconnect_all()` allows a non-superuser to close superuser-opened connections in the same backend** (comment at lines 2576-2584 explicitly flags this). The comment ends with "XXX As of now we don't see any security risk doing this. But we should set some restrictions on that, for example, prevent non-superuser from closing the connections established by superusers even in the same session?" Open question.

### Async cancel discipline on local error

When local query is canceled (`CHECK_FOR_INTERRUPTS` ereports), the `pgfdw_xact_callback(XACT_EVENT_ABORT)` runs → `pgfdw_abort_cleanup` → `PQtransactionStatus == PQTRANS_ACTIVE` triggers `pgfdw_cancel_query`. The cancel request is sent via `libpqsrv_cancel` which is interruptible. **Timeout is 30s** (`CONNECTION_CLEANUP_TIMEOUT`, line 106). If the remote does not respond to the cancel within 30s, the connection is slammed shut and `changing_xact_state` is left true → the entry becomes unusable until backend restart or `postgres_fdw_disconnect`.

### EXPLAIN VERBOSE leak surface

`postgres_fdw_connection(userid, serverid)` returns the FULL libpq connection string including any `password=` from the user mapping. The function is SQL-callable. The catalogs treat user mapping options as readable by the user mapping owner (and the SERVER owner) — so this exposes nothing not already readable from `pg_user_mappings`. But it's a convenience function for an attacker who can call it.

`postgresExplainForeignScan` / `postgresExplainForeignModify` / `postgresExplainDirectModify` print the remote SQL when `es->verbose`. **The remote SQL contains user-mapping `user`?** No — `deparseSelectStmtForRel` does NOT interpolate auth info, only schema-qualified identifiers and `$N` placeholders. Safe.

### Result tuple-descriptor mismatch handling

`make_tuple_from_result_row` (`postgres_fdw.c:8440`) checks `j != PQnfields(res)` at line 8551 and elogs ERROR `"remote query result does not match the foreign table"`. Each column value is fed through `InputFunctionCall` (line 8523) using the LOCAL `attinmeta` — i.e. local type's input function on remote text representation. **A type mismatch (remote `text`, local `int`) → input function reports invalid input syntax with the OFFENDING STRING in the error message** — that IS the remote data leaking into the local error. Mitigation: `conversion_error_callback` (line 8597) adds attname/relname context; the bad value itself comes from the input function and is shown.

## Cross-references

- `source/contrib/postgres_fdw/option.c:194` — `password_required=false` create-time superuser check.
- `source/contrib/postgres_fdw/postgres_fdw.c:8440` — `make_tuple_from_result_row`, the conversion path.
- `source/contrib/dblink/dblink.c` — parallel `dblink_security_check`, `dblink_connstr_check` (referenced at lines 442-443, 752-757).
- `source/src/backend/libpq/auth.c` — `be_gssapi_get_delegation`.
- `source/src/include/libpq/libpq-be-fe-helpers.h` — `libpqsrv_connect_params_start`, `libpqsrv_connect_complete`, `libpqsrv_disconnect`, `libpqsrv_get_result_last`, `libpqsrv_cancel`.
- `source/src/backend/access/transam/xact.c` — `RegisterXactCallback`, `RegisterSubXactCallback`.
- A2 libpq sweep — every `PGconn *` traffic here.

<!-- issues:auto:begin -->
- [Issue register — `postgres_fdw`](../../../issues/postgres_fdw.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `postgres_fdw_disconnect_all` lets non-superuser close superuser-established connections in same backend (XXX in comment at lines 2576-2584). Could be used for a local DoS (close a long-running superuser query's conn mid-flight). (likely)] — `source/contrib/postgres_fdw/connection.c:2587`.
- [ISSUE-security: `configure_remote_session` is one-shot at connect; line 802-809 comment admits a malicious remote view/`set_config` can subvert the session config. No defensive re-check. (defense-in-depth maybe)] — `source/contrib/postgres_fdw/connection.c:811`.
- [ISSUE-security: `pgfdw_report_internal` echoes remote PG_DIAG_MESSAGE_PRIMARY verbatim to local logs via `errmsg_internal` (line 1156). If remote error text contains tuple data (e.g. unique-violation messages name the offending key value), the data leaks to local logs even if local user lacks RLS visibility into the offending row. (likely)] — `source/contrib/postgres_fdw/connection.c:1153`.
- [ISSUE-correctness: `cursor_number = 0` reset at the end of every top-xact (line 1316). But `prep_stmt_number` never resets (line 1056 comment is intentional). After 4B prepared statements in one session, wraparound to 0 could collide with a still-alive remote prep stmt. Comment at line 1038 says "wraparound highly improbable" — for a 100M-stmt/day OLTP it's a real number after 40 days. (nit)] — `source/contrib/postgres_fdw/connection.c:1056`.
- [ISSUE-concurrency: parallel-commit (`parallel_commit=true`) is NOT 2PC. If commit on remote A succeeds, then commit on remote B fails (timeout, ERROR), local sees the failure and ABORTs locally. **A's changes stand, B's are rolled back.** The split-brain risk is documented in the postgres_fdw docs as an acknowledged tradeoff for speed, but reviewers should know. (likely — by design)] — `source/contrib/postgres_fdw/connection.c:1216`.
- [ISSUE-concurrency: `pgfdw_security_check` runs ONCE post-connect. If a connection later experiences libpq auth-refresh (none today, but conceivable with SCRAM rekey), the check is not re-applied. (nit)] — `source/contrib/postgres_fdw/connection.c:446`.
- [ISSUE-error-handling: `do_sql_command_end` at line 873-874 calls `PQconsumeInput` and `pgfdw_get_result`, but `pgfdw_get_result` is a synchronous block (`libpqsrv_get_result_last`). If a malicious remote sends a NoticeResponse loop, the wait_event is set but the client blocks indefinitely; depends on `CHECK_FOR_INTERRUPTS` inside libpq. (maybe)] — `source/contrib/postgres_fdw/connection.c:863`.
- [ISSUE-error-handling: `disconnect_pg_server` (line 689) is called inside `PG_CATCH` of `connect_pg_server` (line 678) — IF the `libpqsrv_connect_params_start` returned non-NULL but the cleanup path throws (e.g. OOM in `pfree(keywords)`), we'd reach `libpqsrv_disconnect(conn)` with conn ostensibly valid. Looks correct, but the `volatile PGconn *conn = NULL` (line 631) plus the `start_conn = libpqsrv_connect_params_start(...); ... conn = start_conn;` assignment-after-success is subtle. If `libpqsrv_connect_complete` ereports, `conn` is still NULL — `libpqsrv_disconnect(NULL)` had better be safe. (nit)] — `source/contrib/postgres_fdw/connection.c:628-684`.
- [ISSUE-correctness: `CONNECTION_CLEANUP_TIMEOUT=30000` is hard-coded (line 106). A high-latency cross-region remote that takes 35s to ACK a cancel will be permanently poisoned (`changing_xact_state=true` stuck). Should be a server-level option. (likely)] — `source/contrib/postgres_fdw/connection.c:106`.
- [ISSUE-defense-in-depth: `appendEscapedValue` (line 2457) used by `postgres_fdw_connection` does double-quote-escape backslash and apostrophe correctly. However, the function emits the FULL conninfo with ANY password embedded if the user mapping has `password=`. Catalog ACL protects this — only mapping owner / server owner can call — but defensive in case ACL was relaxed. (nit)] — `source/contrib/postgres_fdw/connection.c:2456-2467`.
- [ISSUE-audit-gap: no audit log entry on connection open / close to a foreign server. A cross-cluster connection is a security-relevant event; an extension hook would let monitoring catch unexpected loopback connections. (likely — defense-in-depth)] — `source/contrib/postgres_fdw/connection.c:628`.
- [ISSUE-correctness: `pgfdw_inval_callback` at lines 1471-1478 closes the connection if `xact_depth == 0`, else just marks `invalidated`. There's a race window: a concurrent `ALTER USER MAPPING` to change `password=` could fire the inval, and a query started AFTER the inval but BEFORE the next-tx close would still use the old conn (because `entry->xact_depth=0` at start of tx, `make_new_connection` runs, but `invalidated` was cleared in `make_new_connection` line 392 — OK actually). Re-reading: when invalidated and xact_depth==0, disconnect_pg_server is called; next GetConnection finds entry->conn==NULL and calls make_new_connection. Correct. (nit — but the logic is fiddly).] — `source/contrib/postgres_fdw/connection.c:1442`.
- [ISSUE-defense-in-depth: SCRAM pass-through (`use_scram_passthrough`) enforces `require_auth=scram-sha-256` (line 612). Good — prevents MITM downgrade. But this only kicks in IF `use_scram_passthrough` is enabled; the default is NO SCRAM passthrough, and the default `sslmode` (set elsewhere — libpq's default `prefer`) is downgrade-vulnerable on the wire. (likely)] — `source/contrib/postgres_fdw/connection.c:611`.
- [ISSUE-correctness: `XACT_EVENT_PRE_PREPARE` errors unconditionally (line 1260). Comment says "later we might allow read-only cases" — read-only remote xacts could in principle be PREPAREd. Today, ANY operation on a postgres_fdw foreign table inside a 2PC-using local xact will fail. (documented limitation)] — `source/contrib/postgres_fdw/connection.c:1249-1262`.
- [ISSUE-correctness: `pgfdw_xact_callback` walks the whole hash on every xact event even if no postgres_fdw query touched them. Mitigated by `xact_got_connection` flag (line 1181) — quick-exit. Good. (resolved)] — `source/contrib/postgres_fdw/connection.c:1181`.
- [ISSUE-correctness: in `make_new_connection` line 433, `connect_pg_server` is called BEFORE the entry's `keep_connections / parallel_commit / parallel_abort` are read from the syscache (lines 420-430 happen first — actually OK). But re-reading lines 417-431: those are set from `server->options`. So if `keep_connections` is changed by ALTER SERVER, the change takes effect on NEXT connection only (via inval-driven disconnect). Comment at lines 413-414 documents this. (resolved)] — `source/contrib/postgres_fdw/connection.c:413-431`.
