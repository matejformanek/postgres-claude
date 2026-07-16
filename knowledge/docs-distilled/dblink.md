---
source_url: https://www.postgresql.org/docs/current/dblink.html
fetched_at: 2026-07-15T20:50:00Z
anchor_sha: 8f71f64deee6
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.10 dblink — connect to other PostgreSQL databases from within a database"
maps_to_skill: [fdw-development, fmgr-and-spi, wire-protocol]
---

# Docs distilled — dblink (imperative remote-query contrib over libpq)

The *imperative* remote-query module: open a libpq connection, run queries/exec
commands, page results through remote cursors, or fire queries asynchronously
and poll for results. The docs explicitly steer new code to `postgres_fdw`
(declarative, planner-integrated) — dblink survives for procedural,
multi-connection, or fire-and-poll patterns the FDW can't express.

## Non-obvious claims

- **Connections are session-lifetime and either named or unnamed.** Many named
  connections coexist; there is exactly **one** unnamed connection and opening a
  new one *replaces* it. Both signatures exist:
  `dblink_connect(connstr)` and `dblink_connect(connname, connstr)`. Connections
  persist until `dblink_disconnect` or session end. [from-docs]
- **`connstr` is a libpq conninfo string *or* a foreign-server name.** Using a
  server created with `dblink_fdw`/`postgres_fdw` (plus a user mapping) is the
  recommended form — the password comes from the mapping instead of a
  cleartext conninfo. [from-docs]
- **Non-superusers must authenticate with a password.** If the remote does not
  request one, the connect fails: `ERROR: password is required / DETAIL:
  Non-superuser cannot connect if the server does not request a password.` This
  blocks a non-superuser from riding the server's ambient credentials (peer,
  trust, `.pgpass`). `dblink_connect_u` is the **unrestricted** variant that
  waives this — superuser-only by default, `EXECUTE` revoked from `PUBLIC`; grant
  it only with care. [from-docs]
- **SCRAM pass-through** avoids storing cleartext remote passwords: the
  `dblink_fdw` option `use_scram_passthrough` lets dblink present SCRAM-hashed
  secrets rather than a plaintext password in the catalogs. [from-docs]
- **Synchronous vs. async are distinct APIs.** Sync: `dblink(sql)` (returns
  rows), `dblink_exec(sql)` (returns status). Async:
  `dblink_send_query` → `dblink_is_busy` (poll) → `dblink_get_result` (blocks for
  the row set), with `dblink_cancel_query` to abort and `dblink_get_notify` to
  drain LISTEN/NOTIFY that arrived on the connection. One async query per
  connection at a time. [from-docs]
- **Remote cursors require a remote transaction.** `dblink_open` /
  `dblink_fetch` / `dblink_close` page a result set, but a cursor only lives
  inside a transaction on the *remote* side — dblink opens one implicitly if
  none is active, and that has commit-visibility implications across the calls.
  [from-docs]
- **SQL-builder + metadata helpers.** `dblink_get_pkey(relname)` returns the
  primary-key column positions/names; `dblink_build_sql_insert/update/delete`
  synthesize DML text from a local tuple + key, the classic "replicate one row
  to a peer" helper set. `dblink_get_connections()` lists open named
  connections; `dblink_error_message(conn)` returns the last libpq error.
  [from-docs]
- **Three Extension wait events** surface dblink blocking in `pg_stat_activity`:
  `DblinkConnect` (establishing), `DblinkGetConnect` (connection-not-found
  lookup), `DblinkGetResult` (awaiting rows). [from-docs]
- **Connection-name hygiene.** Avoid `=` in a connection name — it can be
  confused with conninfo syntax; and strip publicly-writable schemas from the
  remote `search_path` (`options=-csearch_path=`) when connecting as/for
  untrusted users. [from-docs]

## Links into corpus

- `[[docs-distilled/postgres-fdw.md]]` — the declarative successor; postgres_fdw
  pushes joins/quals through the planner, dblink is procedural. Both sit on
  libpq and can share `postgres_fdw`/`dblink_fdw` servers + user mappings.
- `[[docs-distilled/fdwhandler.md]]` + `[[docs-distilled/fdw-callbacks.md]]` —
  the FDW machinery dblink deliberately *doesn't* use (no plan integration).
- `[[docs-distilled/protocol-flow.md]]` — the async `send_query`/`is_busy`/
  `get_result` split mirrors libpq's non-blocking `PQsendQuery`/`PQisBusy`/
  `PQgetResult` over the wire protocol.
- `fdw-development` / `fmgr-and-spi` skills — dblink is the "call libpq from
  backend C and return `SETOF record`" reference, contrasted against the
  FdwRoutine planner-integrated path.
