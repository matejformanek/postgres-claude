---
source_url: https://www.postgresql.org/docs/current/runtime-config-logging.html
fetched_at: 2026-07-02T20:58:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Error Reporting and Logging (§20.8)

The logging GUC reference — the developer's window into a running backend.
Sections: Where / When / What to Log, CSV, JSON, Process Title. Companion:
`knowledge/docs-distilled/error-message-reporting.md`, skill `debugging`.

## log_min_messages ≠ client_min_messages (the LOG-rank inversion)

- **`log_min_messages` (default `WARNING`, SIGHUP, superuser)** — the
  server-log severity floor. Ladder: `DEBUG5..DEBUG1, INFO, NOTICE, WARNING,
  ERROR, LOG, FATAL, PANIC`. **Crucially, `LOG` ranks ABOVE `ERROR` here but
  BELOW `NOTICE` in `client_min_messages`** — the one place the two ladders
  disagree, so a `LOG` message can go to the server log but never the client.
  [from-docs]
- **`log_min_error_statement` (default `ERROR`, SIGHUP)** — logs the offending
  SQL when an error at/above this level fires; set `PANIC` to suppress. [from-docs]

## Duration logging — the sampling override chain

- **`log_min_duration_statement` (ms, −1=off, SIGHUP)** logs text+duration of
  any statement over the threshold and **overrides** the sampler:
  **`log_min_duration_sample` (ms, −1)** + **`log_statement_sample_rate`
  (1.0)** stochastically log a fraction of statements over a *lower* bar. A
  query past `log_min_duration_statement` is always logged (never sampled out).
  **`log_transaction_sample_rate` (0)** logs *every* statement in a sampled
  fraction of transactions, duration-independent. [from-docs]

## log_statement classes + what escapes them

- **`log_statement` (none/ddl/mod/all, default `none`, SIGHUP)** — `ddl` =
  CREATE/ALTER/DROP; `mod` = ddl + INSERT/UPDATE/DELETE/TRUNCATE/COPY FROM.
  **Syntax errors are NOT logged** (the parse must succeed to classify the
  statement) — a recurring "why isn't my bad query in the log?" surprise; use
  `log_min_error_statement` for those. May leak plaintext passwords. [from-docs]

## log_line_prefix — the %-escapes a hacker actually reads

- **`log_line_prefix` (default `'%m [%p] '`, POSTMASTER)**. Debug-relevant
  escapes: `%p` PID, `%m` ms-timestamp, `%x` transaction id (0 if none), `%v`
  **virtual xid `procNumber/localXID`** (the vxid that shows in
  `pg_locks`/`pg_stat_activity`), `%c` session id (quasi-unique PID+start-time
  hex.hex), `%e` SQLSTATE, `%a` application_name, `%b` backend type, `%P`
  **parallel-group leader PID** (ties a worker to its Gather), `%Q` query id
  (needs `compute_query_id`; **always 0 in `log_statement` output** because the
  id is computed after parse), `%q` = split point that suppresses everything
  after it in non-session processes. [from-docs]

## Lock / recovery / maintenance logging (all keyed off deadlock_timeout)

- **`log_lock_waits` (off, SIGHUP)** logs a wait exceeding **`deadlock_timeout`**
  — same threshold the deadlock detector uses (see `runtime-config-locks.md`).
  **`log_recovery_conflict_waits` (off, POSTMASTER)** does the same for the
  startup process during recovery conflicts. **`log_lock_failures` (off)** logs
  `SELECT ... NOWAIT` lock-acquire failures. [from-docs]
- **`log_autovacuum_min_duration` (default `10min`, SIGHUP, per-table
  overridable)** — logs autovacuum actions over the threshold **and** actions
  skipped for a lock conflict or concurrent drop; `0` logs all. **`log_checkpoints`
  (default `on`)** emits buffers-written / write-time stats. **`log_temp_files`
  (−1)** logs spill files at/over a KB size (`0` = all). [from-docs]

## Verbosity, destination, collector

- **`log_error_verbosity` (TERSE/DEFAULT/VERBOSE, SIGHUP)** — **VERBOSE adds the
  SQLSTATE plus the source `file:function:line`** that raised the error — the
  fastest way to find an ereport's call site without `backtrace_functions`.
  TERSE drops DETAIL/HINT/QUERY/CONTEXT. [from-docs]
- **`log_destination` (default `stderr`, POSTMASTER)** — `stderr, csvlog,
  jsonlog, syslog, eventlog`; **`csvlog`/`jsonlog` require `logging_collector`**.
  **`logging_collector` (off, POSTMASTER)** is the process that captures stderr
  to rotating files and is designed to never drop a message (may block backends
  under load). [from-docs]
- **`log_connections` (BACKEND, superuser, session-start)** — now a
  comma-list (`receipt,authentication,authorization,setup_durations,all`);
  `setup_durations` reports fork + auth + total setup time. Legacy `on/off`
  still accepted. `%` note: psql may connect twice (password probe). [from-docs]
- **`log_parameter_max_length` (−1, SIGHUP)** trims bind params in normal logs
  (`0` disables param logging); **`log_parameter_max_length_on_error` (0)** does
  the same for error logs (`−1` = full) at the cost of storing the textual param
  form at statement start. **`log_startup_progress_interval` (10s, POSTMASTER)**
  logs progress of slow startup steps (dir fsync, unlogged-reln reset).
  [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/error-message-reporting.md]] — the ereport machinery whose output these route.
- [[knowledge/docs-distilled/runtime-config-developer.md]] — `backtrace_functions` complements `log_error_verbosity=VERBOSE`.
- [[knowledge/docs-distilled/runtime-config-locks.md]] — `deadlock_timeout` keys `log_lock_waits`.
- Skill: `debugging` — reading a backend via the log; `error-handling` — verbosity/SQLSTATE.

## Confidence note

All `[from-docs]` (Error Reporting and Logging chapter, fetched 2026-07-02; page
rendered §19.8 numbering — docs-version skew, slug stable). The `%Q`-always-0-in-
`log_statement`, LOG-rank-inversion, and `log_statement` skips-syntax-errors
facts are stated directly by the page. Escape-code meanings not re-verified
against `elog.c log_line_prefix()` this run.
