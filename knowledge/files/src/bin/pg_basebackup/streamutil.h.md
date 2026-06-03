# streamutil.h

## Purpose

Declarations for the connection-handling and replication-command
helpers shared by `pg_basebackup`, `pg_receivewal`, and `pg_recvlogical`.

## Globals exposed

`progname`, `connection_string`, `dbhost`, `dbuser`, `dbport`, `dbname`,
`dbgetpassword`, `WalSegSz`, `conn` — file-scope process globals living
in `streamutil.c`. Each tool sets them from getopt parsing and then
calls `GetConnection()`.
`source/src/bin/pg_basebackup/streamutil.h:20-30`

## Public API

- `GetConnection()` — build a `PGconn` from the globals. Loops for
  password retries. Validates `integer_datetimes`. Runs
  `ALWAYS_SECURE_SEARCH_PATH_SQL` on dbname (SQL) connections.
  `streamutil.h:32`
- `CreateReplicationSlot()` / `DropReplicationSlot()` — wrap the
  replication-protocol DDL with old-and-new option-syntax handling
  (`(OPT, OPT)` from v15+, otherwise space-separated keywords).
  `streamutil.h:35,40`
- `RunIdentifySystem()` — issue `IDENTIFY_SYSTEM` and parse
  sysident / starttli / startpos / dbname out of the response.
  `streamutil.h:41`
- `GetSlotInformation()` — `READ_REPLICATION_SLOT` for the named
  physical slot, returning `restart_lsn` + `restart_tli`.
  `streamutil.h:56`
- `RetrieveWalSegSize(conn)` — `SHOW wal_segment_size` parse →
  global `WalSegSz`. v10+ only; default 16MB for older. `streamutil.h:59`
- `AppendPlainCommandOption / AppendStringCommandOption / AppendIntegerCommandOption`
  — query builders for replication-protocol commands. `streamutil.h:46-54`
- `feGetCurrentTimestamp() / feTimestampDifference() / feTimestampDifferenceExceeds()` —
  frontend reimplementations because libpq won't link backend timestamp code.
  `streamutil.h:60-65`
- `fe_sendint64 / fe_recvint64` — network-byte-order int64 helpers
  used to read CopyData feedback messages. `streamutil.h:66-67`

## Phase D notes

- `dbgetpassword` is a tri-state int (0 auto, -1 never, 1 always) —
  this matches `-w` / `-W` / default. See `streamutil.c:154` and
  the comment at `streamutil.h:26`.
- `conn` global means PG-wide tools all share one connection
  pointer per process — convenient for `disconnect_atexit` cleanups
  in each tool, but means anything that calls `GetConnection()`
  *and* also returns the PGconn to the caller produces TWO references
  to the same conn. [verified-by-code]
