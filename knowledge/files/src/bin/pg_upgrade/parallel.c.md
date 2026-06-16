# parallel.c

## Purpose

Coarse-grained multi-process parallelism for two long-running phases:
parallel per-database dump (`parallel_exec_prog` driving multiple
`pg_dump` invocations) and parallel per-tablespace data transfer
(`parallel_transfer_all_new_dbs`). On POSIX uses `fork(2)`; on Windows
uses `_beginthreadex` with a small thread-arg slot array.

## Role in pg_upgrade

- `dump.c:generate_old_dump` uses `parallel_exec_prog` for per-DB
  pg_dump fan-out.
- `transfer.c:transfer_all_new_dbs` (called by `pg_upgrade.c`) uses
  `parallel_transfer_all_new_dbs` for per-tablespace fan-out.
- Both forms gate via `user_opts.jobs <= 1` to fall back to the
  serial path.

Different from `task.c` which parallelizes catalog queries via libpq
async APIs (single-process, multi-connection). parallel.c is
multi-process / multi-thread.

## Key functions

- `parallel_exec_prog(log_file, opt_log_file, fmt, ...)` `parallel.c:63`
  — same API as exec_prog but parallel-aware. On `jobs > 1` it forks
  a child that runs `exec_prog(...)`; parent updates
  `parallel_jobs++` and returns. The child path uses `_exit` to skip
  atexit handlers (line 125) — critically, this prevents the child
  from running `stop_postmaster_atexit` which would kill the server
  the parent is using.
- `parallel_transfer_all_new_dbs(old, new, old_pgdata, new_pgdata,
  old_tblspc, new_tblspc)` `parallel.c:173` — fork-and-run
  `transfer_all_new_dbs` per tablespace.
- `reap_child(wait_for_child)` `parallel.c:281` — `waitpid(-1, ...,
  wait ? 0 : WNOHANG)`. Returns false on no children. Fatal on
  abnormal child exit (any nonzero status).
- Windows: `win32_exec_prog`, `win32_transfer_all_new_dbs` thread
  entrypoints (line 154, 264). `cur_thread_args` swap dance in
  reap_child (line 322-336) keeps the args array compacted.

## State / globals

- `parallel_jobs` — count of in-flight children (line 19).
- Windows: `thread_handles` (HANDLE array), `exec_thread_args`,
  `transfer_thread_args`, `cur_thread_args` — pre-allocated slot
  arrays.

## Phase D notes

[from-code] **Fork model + atexit**: child uses `_exit` instead of
`exit` (line 125, 232) to skip `stop_postmaster_atexit`. Critical
correctness: without this, a failed pg_dump in the child would
trigger the atexit hook which would invoke `pg_ctl stop` on the
parent's running postmaster — race condition with the parent's
other workers.

[from-code] **Stdio quiesce**: `fflush(NULL)` before fork (line 119,
222) — forks the parent's flushed stdio state. Otherwise stdout
buffer contents would be duplicated across both parent and children
on exit.

[from-code] **`reap_child` fatal-on-nonzero** (line 300): "child
process exited abnormally: status %d". Means ANY pg_dump failure or
transfer failure aborts the entire upgrade — no per-db retry.

[from-code] **Race in `parallel_exec_prog`** (line 116): the parent
increments `parallel_jobs` BEFORE the fork. If the fork itself
fails (`child < 0`), `pg_fatal` is called immediately so the
mis-count is harmless. If the child fails before reaching its
`_exit`, that's an asynchronous SIGCHLD which `reap_child` will
catch.

[ISSUE-state-transition: parent does not block SIGINT while forking;
a Ctrl-C between fflush and fork would leave child handles in
ambiguous state (maybe-low)] — `parallel.c:122`. Children inherit
the SIGINT disposition; in practice the upgrade-time setup ensures
SIGINT goes to the process group.

[ISSUE-info-disclosure: per-child log file `log_file` passed by
caller — children all write to caller-named per-db log
(`pg_upgrade_dump_<oid>.log`) which records pg_dump stderr verbatim
(low)] — Same secret-scrub concern as exec.c. Children call back
into exec_prog (line 125, 158).

[from-code] **`reap_child(true)` blocking call** (line 295): used at
end of `generate_old_dump` to wait for ALL children. waitpid(-1)
without WNOHANG. Fine because parent has nothing else to do.

[from-code] **Windows transfer_thread_arg** (line 244-250): caller's
string pointers (`old_pgdata`, etc.) are `pg_strdup`'d into the
slot's `transfer_thread_arg`. POSIX path passes them through fork(2)
unchanged because each forked process gets its own copy.

[ISSUE-correctness: Windows path's `cur_thread_args` swap (line
334-336) relies on the assumption that the dead thread no longer
touches its old slot pointer (low)] — Comment at line 327 calls this
out; "we can safely swap the struct pointers within the array"
because the now-dead thread has already returned.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
