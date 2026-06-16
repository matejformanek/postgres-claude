# streamutil.c

## Purpose

Connection-and-replication-command helpers shared by `pg_basebackup`,
`pg_receivewal`, and `pg_recvlogical`. Owns the global `PGconn *conn`,
password retry loop, replication-slot DDL wrappers,
`IDENTIFY_SYSTEM` / `READ_REPLICATION_SLOT` parsers, and
network-byte-order int64 helpers.

## Role in pg_basebackup

Front-door layer between getopt-parsed connection options and a
working replication PGconn. Every tool's `main()` populates the
`connection_string` / `dbhost` / `dbuser` / `dbport` / `dbgetpassword`
globals then calls `GetConnection()`.

## Wire/protocol surface

- `GetConnection()` consumes the user-supplied conninfo string (parsed
  by `PQconninfoParse`) and library defaults. Issues
  `SHOW data_directory_mode`, `SHOW wal_segment_size`, and
  `ALWAYS_SECURE_SEARCH_PATH_SQL` on the new connection. Trusts the
  server's responses to set process-wide permission and segment-size
  globals.
- `RetrieveWalSegSize()` parses the server's `SHOW wal_segment_size`
  output via `sscanf(... "%d%2s")` and validates with
  `IsValidWalSegSize` (1MB..1GB, power of two). `streamutil.c:312-338`
- `RunIdentifySystem()` parses the `IDENTIFY_SYSTEM` response: sysid
  (string copied), starttli (atoi), startpos (`%X/%08X` sscanf),
  db_name (string copied). `streamutil.c:419-477`
- `GetSlotInformation()` parses `READ_REPLICATION_SLOT` (slot_type,
  restart_lsn, restart_tli). Refuses non-physical slots
  (`streamutil.c:540-546`).

## Key functions

- `GetConnection()` `streamutil.c:59` — the connection builder. Loops on
  `CONNECTION_BAD + PQconnectionNeedsPassword + dbgetpassword != -1`,
  calling `simple_prompt("Password: ", false)` to get a fresh password
  (line 162). Reuses across retries. After connect, runs:
  - `ALWAYS_SECURE_SEARCH_PATH_SQL` (line 227) if `dbname != NULL` and
    server is v10+ — anti-search-path-hijack guard.
  - integer_datetimes check (line 243) — refuses non-matching
    timestamp encoding.
  - `RetrieveDataDirCreatePerm()` (line 262) — for v11+, fetch
    `data_directory_mode` and call `SetDataDirectoryCreatePerm()` so
    locally-created files match server's umask.
- `RetrieveWalSegSize(conn)` `streamutil.c:276`
- `RunIdentifySystem(conn, &sysid, &starttli, &startpos, &db_name)`
  `streamutil.c:409`
- `GetSlotInformation(conn, slot_name, &restart_lsn, &restart_tli)`
  `streamutil.c:490`
- `CreateReplicationSlot(...)` `streamutil.c:584` — handles old
  vs new option syntax based on server version; explicit
  `slot_exists_ok` knob suppresses `ERRCODE_DUPLICATE_OBJECT`.
- `DropReplicationSlot(conn, slot_name)` `streamutil.c:697`
- `AppendPlainCommandOption` / `AppendStringCommandOption` /
  `AppendIntegerCommandOption` `streamutil.c:746,767,790` — query
  builders. `AppendStringCommandOption` runs values through
  `PQescapeStringConn`.
- `feGetCurrentTimestamp / feTimestampDifference / feTimestampDifferenceExceeds`
  `streamutil.c:803,822,844` — frontend reimplementations.
- `fe_sendint64 / fe_recvint64` `streamutil.c:857,868` — used by
  receivelog.c for replication-feedback packets.

## State / globals

File-scope: `WalSegSz` (the server-reported segment size, used by
`receivelog.c`), `progname`, `connection_string`, `dbhost`, `dbuser`,
`dbport`, `dbname`, `dbgetpassword`, `password` (static, scrubbed
*before* `simple_prompt` reassigns: `free(password)` at line 161 then
overwritten by next prompt), `conn`.

## Phase D notes

[ISSUE-secret-scrub: password stored in process-global static `password`
across reconnects, never zeroed before free (maybe)] —
`streamutil.c:51` declares `static char *password = NULL`. Line 161
does `free(password)` before reading a new one but never
`explicit_bzero` first. After the connection succeeds, `password`
remains in heap memory until the next reconnect (which usually never
happens in pg_basebackup). pg_recvlogical and pg_receivewal may
reconnect; in those cases the prior password's memory is freed but
unscrubbed. libpq itself stores its own copy inside PGconn. Comparable
to the libpq-frontend findings — a memory-disclosure attacker reading
freed heap can still see the credential. [verified-by-code]

[ISSUE-trust-boundary: server-reported `wal_segment_size` becomes
process-wide `WalSegSz` used to address files
(state-transition, maybe)] — `RetrieveWalSegSize` does validate with
`IsValidWalSegSize` (1MB..1GB, power of two) — so a malicious server
can't set it to 0 or 2GB. But within those bounds the server picks
the segment size used to compute filenames, padding, segment
boundaries (`XLogSegmentOffset`), and the validate-existing-file check
in `open_walfile`. A compromised server could announce a different
segment size than the actual cluster runs at, causing the local WAL
archive to be misshapen. Standalone replay of resulting files would
fail; not a code-execution risk. [verified-by-code]

[ISSUE-trust-boundary: server-reported `data_directory_mode` sets
local file-creation umask (info-disclosure, low)] —
`RetrieveDataDirCreatePerm()` parses an octal mode and calls
`SetDataDirectoryCreatePerm`. The only validation is "did sscanf
succeed" (line 385). A malicious or buggy server could announce mode
0777, causing the local backup to be world-readable. The mode is then
applied to ALL files we create for this backup (data + WAL).
[verified-by-code]

[ISSUE-undocumented-invariant: `simple_prompt(prompt, echo=false)`
returns a malloc'd string that may not survive `PQfinish` on its
own — Assert `dbname == NULL || connection_string == NULL` at line
78 (state-transition, low)] — comment line 75-77 explains why; if a
new tool wires both at once, the assert fires only in cassert builds.

`integer_datetimes` mismatch causes `exit(1)` (line 254). Pre-2008
servers won't match modern clients; harmless modern.

`ALWAYS_SECURE_SEARCH_PATH_SQL` is only set on SQL (`dbname != NULL`)
connections (line 223). Pure replication connections don't run SQL
so the search_path attack surface doesn't apply. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
