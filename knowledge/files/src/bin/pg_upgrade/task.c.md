# task.c

## Purpose

Parallelizes "once-in-each-database" catalog queries via a single-
process, multi-connection libpq state machine. Slots progress
FREE → CONNECTING → RUNNING_QUERIES → FREE while `select(2)` waits on
ready sockets, so up to `user_opts.jobs` connections run concurrently
without forking.

## Role in pg_upgrade

The "task" abstraction used by check.c data-type-usage scans, info.c
schema info dump, function.c loadable-libraries query, and version.c
extension-update report. Distinct from parallel.c (which is fork/
thread + subprocess) — task.c stays in one process.

## Key functions

- `upgrade_task_create()` `task.c:117` — allocates an `UpgradeTask`
  and prepends `ALWAYS_SECURE_SEARCH_PATH_SQL` as step 0 (line 124).
  Every task starts by setting a safe search_path on the new
  connection.
- `upgrade_task_add_step(task, query, process_cb, free_result, arg)`
  `task.c:151` — appends a `UpgradeTaskStep` and concatenates the
  query text into `task->queries` with a trailing `;`. Multiple
  steps form one batch sent via a single `PQsendQuery`.
- `upgrade_task_run(task, cluster)` `task.c:421` — main loop. Iterate
  `process_slot` over every slot, then `wait_on_slots` via select(2)
  until `dbs_complete == cluster->dbarr.ndbs`.
- `start_conn(cluster, slot)` `task.c:174` — builds conninfo string
  the same way as `server.c::get_db_conn` (db, user, port, sockdir,
  optional max_protocol_version=3.0), then `PQconnectStart`. Async
  no-block.
- `process_slot(cluster, slot, task)` `task.c:236` — state machine
  switch. CONNECTING: `PQconnectPoll`. RUNNING_QUERIES:
  `PQconsumeInput` then drain `PQgetResult` for each step.
- `process_query_result(...)` `task.c:207` — runs the step's
  `process_cb`, optionally `PQclear`s the result.
- `wait_on_slots(slots, numslots)` `task.c:365` — builds fd_sets per
  slot's `select_mode` (read after CONNECTING done, read while
  running) and blocks on `select(maxFd+1, ...)`.
- `select_loop(maxFd, &in, &out)` `task.c:332` — EINTR-restart wrapper.

## State / globals

Static file-scope:
- `dbs_complete` — count of databases fully processed.
- `dbs_processing` — index of next DB to assign.

Both are reset at start of every `upgrade_task_run`. Since pg_upgrade
is single-threaded, only one task runs at a time.

## Phase D notes

[from-code] **No password auth** — `start_conn` uses
`PQconnectStart`, same trust-auth assumption as server.c. No password
strings in process memory.

[from-code] **First query is always `ALWAYS_SECURE_SEARCH_PATH_SQL`**
(line 124) — anti-search-path-hijack guard. A malicious template1
search_path could otherwise redirect catalog queries.

[from-code] **Batch query string growth.** Multiple steps' queries
are concatenated into one `PQexec`-style batch (line 165:
`appendPQExpBuffer(task->queries, "%s;", query)`). All steps execute
in one server roundtrip; results are drained step by step in
`process_query_result`. If any single query in the batch fails,
subsequent step callbacks never run because `PQresultStatus !=
TUPLES_OK/COMMAND_OK` triggers `pg_fatal`.

[ISSUE-trust-boundary: per-database connection inherits whatever
GUCs the OLD/NEW cluster sets in `postgresql.conf`. The
search_path-set is the only defense; ALTER DATABASE SET role/
search_path could still confuse caller-supplied queries
(maybe-low)] — `task.c:124`. Mitigated by always running
`ALWAYS_SECURE_SEARCH_PATH_SQL` first.

[from-code] **Fatal-on-any-error** (line 218, 269, 284, 295): any
libpq error in any slot aborts the whole upgrade. No per-DB retry.
`PQerrorMessage(conn)` is interpolated raw into `pg_fatal` —
contains server-side message text. Same secret-scrub note as
util.c.

[ISSUE-secret-scrub: `pg_fatal("connection failure: %s",
PQerrorMessage(slot->conn))` (lines 218, 269, 284, 295) leaks the
server's error text into the upgrade log (low)] — Standard libpq
behavior.

[from-code] **Slot recycling** (line 319-322): on completion, slot
is `memset(0)` then immediately re-entered via recursive
`process_slot` call to start the NEXT db without waiting for the
next select(2). Avoids latency for short queries.

[ISSUE-correctness: `wait_on_slots` skips FREE slots silently (line
389-390) — comment claims "we'll never use these slots again"
because they're free only at end-of-run. The comment is true given
the recursive recycling above, but a future refactor could violate
it (low)] — `task.c:389`.

[from-code] **`select(2)` not poll/epoll** — POSIX-portable choice.
maxFd cap is the libpq socket count, which is `user_opts.jobs` (a
small integer); no FD_SETSIZE risk in practice.
