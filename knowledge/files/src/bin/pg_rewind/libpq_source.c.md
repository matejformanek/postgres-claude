# libpq_source.c

**Source:** `source/src/bin/pg_rewind/libpq_source.c` (685 lines)

## Purpose

Concrete `rewind_source` implementation that fetches data from a live
remote PostgreSQL server via a libpq connection. Uses the existing
SQL-callable functions `pg_ls_dir()`, `pg_stat_file()`,
`pg_read_binary_file()`, `pg_current_wal_insert_lsn()`, and
`pg_tablespace_location()` rather than a custom replication
sub-protocol. Files are streamed in `MAX_CHUNK_SIZE` (1 MiB) chunks
batched up to `MAX_CHUNKS_PER_QUERY` (1000) per prepared-statement
execution. [verified-by-code]

Sister file: `local_source.c` (4.6K, not in this batch) provides the
same vtable for a filesystem-only source.

## Role in pg_rewind

This is **the wire-protocol surface** for the remote-source case.
Created in `pg_rewind.c:319` after a successful `PQconnectdb`. The
PGconn was opened by the caller (so this file does not handle
authentication, prompting, or password input — pg_rewind has no
`simple_prompt` callsite at all). All bytes that end up overwriting
target data-directory files pass through `process_queued_fetch_requests`
or `libpq_fetch_file` in this file.

## Key functions

- `init_libpq_source(conn)` — `libpq_source.c:80-104`. Allocates the
  `libpq_source` struct, wires the seven function pointers, stores
  the PGconn, init three StringInfos for batch-query construction.
  Calls `init_libpq_conn(conn)` to configure the session.
  [verified-by-code]
- `init_libpq_conn(conn)` — `libpq_source.c:109-155`. Defensive
  session setup:
  - Disables `statement_timeout`, `lock_timeout`,
    `idle_in_transaction_session_timeout`, `transaction_timeout`.
  - `SET default_transaction_read_only = on`.
  - `SET search_path = ''` via `ALWAYS_SECURE_SEARCH_PATH_SQL`.
  - Checks `SHOW full_page_writes`; fatal if not `on`. (Reason: torn
    pages from concurrent writes are repaired only by FPIs in WAL —
    libpq_source.c:134-141 comment.)
  - `PQprepare`s `fetch_chunks_stmt` taking three array params
    `(path text[], begin int8[], len int4[])` and returning
    `(path, begin, chunk bytea)` rows.
  [verified-by-code]
- `run_simple_query(conn, sql)` — `libpq_source.c:162-183`. Asserts
  single-row, single-column, non-null. Returns `pg_strdup`'d cell.
- `run_simple_command(conn, sql)` — `libpq_source.c:190-202`. Expects
  `PGRES_COMMAND_OK`, fatal otherwise.
- `libpq_get_current_wal_insert_lsn(source)` —
  `libpq_source.c:207-226`. Runs `SELECT pg_current_wal_insert_lsn()`,
  parses `"%X/%08X"` and assembles a uint64. [verified-by-code]
- `libpq_traverse_files(source, callback)` —
  `libpq_source.c:231-319`. Sends one huge `WITH RECURSIVE` query
  that walks the source datadir via `pg_ls_dir` + `pg_stat_file`,
  left-joined with `pg_tablespace` to fetch link targets. Result
  columns: `path|filename, size, isdir, link_target`. For each row:
  - Null size → file removed mid-walk → skip.
  - link_target non-empty + absolute → `FILE_TYPE_SYMLINK`.
  - link_target non-empty + relative → `FILE_TYPE_DIRECTORY` (in-place
    tablespaces).
  - else isdir? → DIRECTORY else REGULAR.
  - Invokes `process_source_file` callback. [verified-by-code]
- `libpq_queue_fetch_file(source, path, len)` —
  `libpq_source.c:324-349`. Opens (and truncates) the target file
  immediately; queues a range fetch of `Max(len, MAX_CHUNK_SIZE)`
  bytes from offset 0. The "fetch up to 1 MiB even if file is
  smaller" trick covers the case where the source file grew between
  directory scan and copy (lines 326-345 comment). [verified-by-code]
- `libpq_queue_fetch_range(source, path, off, len)` —
  `libpq_source.c:354-414`. Two parts:
  - Coalesce: if the new range continues the last queued range
    (same `path` *pointer* + adjacent offset + previous chunk under
    `MAX_CHUNK_SIZE`), extend the previous request instead of
    enqueueing a new one (lines 369-394).
  - Split: divide remaining bytes into `MAX_CHUNK_SIZE`-sized chunks;
    if the queue hits `MAX_CHUNKS_PER_QUERY`, call
    `process_queued_fetch_requests` to drain. [verified-by-code]
- `libpq_finish_fetch(source)` —
  `libpq_source.c:419-423`. Drains the queue.
- `process_queued_fetch_requests(src)` —
  `libpq_source.c:425-607`. The critical wire transfer:
  - Builds three text-array literals for paths/offsets/lengths.
  - `PQsendQueryPrepared` + `PQsetSingleRowMode` for streaming.
  - For each `PGRES_SINGLE_TUPLE` result row:
    - Reads `path text`, `begin int8` (network byte order, swapped
      via `pg_ntoh64`), `chunk bytea`.
    - If `chunk` is null → source deleted the file → call
      `remove_target_file(filename, missing_ok=true)` and continue.
    - Else verify filename and offset match the requested item
      (fatal on mismatch); fatal if `chunksize > rq->length` (source
      sent more than requested).
    - `open_target_file(filename, trunc=false)` +
      `write_target_range(chunk, chunkoff, chunksize)`.
  - Validates exactly `num_requests` chunks arrived; resets queue.
  [verified-by-code]
- `appendArrayEscapedString(buf, str)` —
  `libpq_source.c:612-628`. Wraps `str` in `"…"` and prepends `\`
  before any `"` or `\` — the array-literal escape used to build
  the SQL `text[]` parameter inline. [verified-by-code]
- `libpq_fetch_file(source, path, *filesize)` —
  `libpq_source.c:633-668`. Single-file read via
  `SELECT pg_read_binary_file($1)`. Returns malloc'd, zero-terminated
  buffer. Used for control files and timeline-history files.
  [verified-by-code]
- `libpq_destroy(source)` — `libpq_source.c:673-684`. Frees the
  three StringInfo buffers and the struct. **Does NOT close the
  PGconn** — caller owns it. [verified-by-code]

## State / globals

No file-static globals. All mutable state lives in the
`libpq_source` struct: `conn`, request queue `request_queue[1000]`,
`num_requests`, and three reused `StringInfoData` buffers.

## Phase D notes

**The wire protocol is "SQL over libpq" — not a custom protocol.**
This means the server-side surface is `pg_read_binary_file()` and
friends, which require either superuser or membership in
`pg_read_server_files` (PG 11+). The privilege check happens on the
server; pg_rewind itself has no concept of "what files am I allowed
to fetch". A compromised source with a privileged role can serve any
file the role can read, and pg_rewind will write those bytes (subject
to `path_is_safe_for_extraction` in file_ops.c) into the target
datadir.

**Authentication boundary:** `PQconnectdb(connstr_source)` in
pg_rewind.c:311. Anything libpq accepts (password, SSL cert, GSS,
SCRAM) works. There is **no callsite of `simple_prompt`** anywhere
in pg_rewind. If the connection string requires a password and none
is provided via `~/.pgpass` or `PGPASSWORD`, libpq itself will issue
its own conninfo `PGCONN_OPT_PASSWORD` handling and may interactively
prompt or fail depending on settings. The "secret-scrub" gap of the
A2/A4/A5 form (where an in-process buffer holds the cleartext
password after prompting) is mostly absent here — but `connstr_source`
itself can contain `password=...` and is held for the entire run
plus passed to `GenerateRecoveryConfig` (see pg_rewind.c notes).

**Trust-the-source for sizes.** Line 583-591 comment is explicit:
"We should not receive more data than we requested, ... We could
receive less, though, if the file was truncated in the source after
we checked its size." So an adversarial source can short-change the
target (resulting in undersized files) but cannot overflow.
`chunksize > rq->length` is fatal.

**Trust-the-source for paths.** The result-set `filename` is
cross-checked against the requested `rq->path` via `strcmp` (line
573-577) — so a hostile source cannot rename files mid-fetch. But
the initial path *was* server-supplied via `libpq_traverse_files`,
so renames are no defense against attacker-named paths in the first
place; `path_is_safe_for_extraction` in `file_ops.c:open_target_file`
is the only check.

**Single-row mode + single connection means request ordering
matters.** The libpq protocol delivers chunks in the order the
prepared statement returns them; pg_rewind asserts that order matches
its `request_queue` via the `chunkno` counter and the
`strcmp(filename, rq->path)` + `chunkoff != rq->offset` checks. If
the server reordered (it doesn't, but a future protocol change
might), the assertion fires.

**Null chunk → unlink.** If `pg_read_binary_file` returns null (file
was deleted on source after directory scan), pg_rewind unlinks the
file on target (`remove_target_file(filename, missing_ok=true)`,
line 566). This is a server-controlled delete primitive: any source
that can race a file deletion can force a target unlink. It is
guarded by `path_is_safe_for_extraction` in
`remove_target_file`, but the surface is real.

**Array-literal escaping is hand-rolled.** `appendArrayEscapedString`
only escapes `"` and `\`. If a future caller put a path containing a
NUL byte through it (filesystem paths can't legally contain NUL on
POSIX, so this is theoretical), the SQL fragment would be truncated.

**WITH RECURSIVE query result depends on `pg_tablespace_location()`
seeing absolute vs relative paths.** In-place tablespaces (relative
paths) are treated as directories not symlinks (lines 304-309) so
they get the standard CREATE/COPY treatment rather than `symlink(2)`.

## Potential issues

- `[ISSUE-trust-boundary: pg_read_binary_file()-returning-null is interpreted as "delete this file from the target" — an attacker-controlled source can use file-deletion-races to force arbitrary target unlinks (modulo path_is_safe_for_extraction in remove_target_file) (medium)]`
- `[ISSUE-wire-protocol: libpq_traverse_files relies on a single non-snapshot WITH RECURSIVE pg_ls_dir() walk; pg_ls_dir/pg_stat_file are not transaction-snapshot consistent, so files appearing/disappearing across recursive iterations produce a non-atomic source snapshot. pg_rewind tolerates missing files (null size → skip, line 286-293) but inconsistencies in directory contents between scan and fetch can still confuse the diff (low)]`
- `[ISSUE-secret-scrub: no scrub of connstr_source memory; if connstr contains "password=", it lives in the process address space the entire run. pg_rewind has no simple_prompt path so there is no separate cleartext buffer, but the connstring itself is the same exposure (maybe)]`
- `[ISSUE-trust-boundary: source can serve files with truncated tail (chunksize < requested length, line 583-591) and pg_rewind writes only the truncated bytes, leaving the target file shorter than the source claimed — possible state-inconsistency vector if the truncation is at a relation file (low)]`
- `[ISSUE-undocumented-invariant: queue_fetch_range coalesces requests by **pointer equality** of path strings (line 363-368), not strcmp; the comment acknowledges this and says it's correctness-safe but performance-affecting. Future refactors must preserve the "caller passes same pointer" invariant (low)]`
- `[ISSUE-dos: MAX_CHUNK_SIZE = 1 MiB and MAX_CHUNKS_PER_QUERY = 1000 mean up to ~1 GiB of bytea result can be materialized server-side per prepared-statement call; a slow client and a large source might OOM the server. No flow control beyond single-row mode (low)]`
- `[ISSUE-undocumented-invariant: init_libpq_conn requires full_page_writes=on but does not check that wal_level is appropriate or that the source has not been recently reset; a freshly-promoted source missing the first checkpoint after promotion can leave timeline edge cases (low)]`
