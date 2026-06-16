# `src/bin/pg_test_fsync/pg_test_fsync.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~650
- **Source:** `source/src/bin/pg_test_fsync/pg_test_fsync.c`

Microbenchmark of supported `fsync()` methods. For a configurable test
duration (default 5 s), runs the same XLOG-block write loop over each
method (`open_datasync`, `fdatasync`, `fsync`, `fsync_writethrough`,
`open_sync` with various write sizes) and prints ops/sec and average
microseconds per op. Helps operators pick `wal_sync_method` (and verify
that `O_DIRECT` works on their filesystem). [from-comment]

## API / entry points

- `main` — `handle_args`, install signal handlers (SIGINT/SIGTERM/SIGHUP
  → cleanup-and-exit; SIGALRM → set `alarm_triggered`), seed PRNG,
  `prepare_buf` (fill the 16 MiB segment-sized buffer with random data),
  `test_open` (validate we can write the test file), `test_sync(1)`,
  `test_sync(2)`, `test_open_syncs`, `test_file_descriptor_sync`,
  `test_non_sync`. Unlinks the file before exit. [verified-by-code]
- `START_TIMER` / `STOP_TIMER` (macros) — set alarm + gettimeofday at
  start; gettimeofday + print_elapse at end. Macros to avoid the cost
  of a function call inside the inner loop. [from-comment]
- `process_alarm` — signal handler that sets `alarm_triggered`. On
  Windows, a thread that sleeps then sets it (no `alarm()`).
  [verified-by-code]
- `signal_cleanup` — `unlink(filename)` if needed, write a newline to
  stdout, `_exit(1)`. [verified-by-code]
- `test_sync(writes_per_op)` — for each of open_datasync, fdatasync,
  fsync, fsync_writethrough, open_sync: loop writing `writes_per_op`
  blocks of `XLOG_BLCKSZ` each, synchronizing per outer iteration.
  Counts ops until alarm fires. [verified-by-code]
- `test_open_sync(msg, write_size_kb)` — same loop but with various
  write sizes (1k / 2k / 4k / 8k / 16k) to show how syscall overhead
  scales. [verified-by-code]
- `test_file_descriptor_sync` — measures whether `fsync()` on a
  different FD for the same file syncs another process's writes; used
  by PG to decide whether multiple backends fsyncing the same WAL file
  is efficient. [from-comment]
- `test_non_sync` — straight `pg_pwrite` loop with no sync, as a baseline.
- `open_direct(path, flags, mode)` — adds `O_DIRECT` if defined; falls
  back to `fcntl(F_NOCACHE)` on macOS. Returns -1 on either failure.
  [verified-by-code]
- `pg_fsync_writethrough(fd)` — `fcntl(fd, F_FULLFSYNC, 0)` on macOS,
  ENOSYS elsewhere. [verified-by-code]
- `print_elapse(start, stop, ops)` — compute ops/sec and µs/op.

## Notable invariants / details

- Tests run on a single file, default `./pg_test_fsync.out`, overridable
  with `-f`. The same file persists across all tests so that filesystem
  caching state is "similar" to what PG sees in production.
  [verified-by-code]
- Buffer is `alignas(PGAlignedXLogBlock)` so O_DIRECT writes line up on
  filesystem boundaries (line 71). [verified-by-code]
- Random buffer contents avoid filesystem compression skewing the test.
  [from-comment]
- The `secs_per_test` value must be > 0 (line 194-196) but is otherwise
  unvalidated above; UINT_MAX seconds is technically accepted and would
  hang. [verified-by-code]
- `test_open_sync` is conditionally compiled out if `O_SYNC` is not
  defined (line 466, 475, 494). On those platforms the labels are still
  printed but with "n/a". [verified-by-code]
- `fs_warning` only gets surfaced after `test_sync`; users running
  `test_open_syncs` first wouldn't know their FS lacks direct-IO.
  [verified-by-code]

## Potential issues

- `pg_test_fsync.c:594-605` — `signal_cleanup` calls `unlink` and
  `write(STDOUT_FILENO, ...)` from a signal handler. `unlink` is not on
  POSIX's async-signal-safe list (though it works on every real OS).
  [ISSUE-correctness: unlink in signal handler is not strictly
  async-signal-safe (nit)]
- `pg_test_fsync.c:71` — `buf[DEFAULT_XLOG_SEG_SIZE]` is statically
  allocated at 16 MiB. On 32-bit or constrained embedded platforms
  this single global makes the binary fat. [ISSUE-style: 16 MiB BSS for
  what's effectively a benchmark (nit)]
- `pg_test_fsync.c:248-249` — `test_open` writes
  `DEFAULT_XLOG_SEG_SIZE` (16 MiB) and fsyncs. If the FS is `ENOSPC`
  the user gets a misleading "write failed" message; the actual cause
  is space. [ISSUE-style: errno already in %m but the message could
  call out ENOSPC specifically (nit)]
- `pg_test_fsync.c:475-490` — `test_open_sync(..., 1)` issues 16
  individual 1k writes per outer loop, each forcing a sync. On
  filesystems with 4k block size and no sub-block-size O_DIRECT support
  this can produce write failures (the comment at line 423-429
  acknowledges this for the larger test_sync). [from-comment]
- The Windows path uses `CreateThread` + `Sleep(secs_per_test * 1000)`
  as the alarm mechanism (line 50-57, 642-650). Thread creation is
  itself measured as overhead in the first iteration.
  [verified-by-code]
- `pg_test_fsync.c:178` — `filename = pg_strdup(optarg);` — small leak
  on subsequent `-f`s; not material for a one-shot benchmark.
  [ISSUE-leak: leaks previous filename if -f given twice (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `bin-singletons`](../../../../issues/bin-singletons.md)
<!-- issues:auto:end -->
