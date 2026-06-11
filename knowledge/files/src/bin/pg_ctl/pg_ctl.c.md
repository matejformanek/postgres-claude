# `src/bin/pg_ctl/pg_ctl.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~2516
- **Source:** `source/src/bin/pg_ctl/pg_ctl.c`

The PostgreSQL postmaster front-end: init, start, stop, restart, reload,
status, promote, logrotate, kill, and (Windows-only) register/unregister/
runservice. On Unix it forks `/bin/sh -c "exec postgres …"`; on Windows it
launches the postmaster inside a restricted token + job object sandbox.
Communicates with the live postmaster mostly via Unix signals and the
`$PGDATA/postmaster.pid` file (whose multi-line v10+ format encodes the
PID, start time, status, and several connectability hints).
[verified-by-code] [from-comment]

## API / entry points

- `main` (line 2201) — parses long options + subcommand verb, refuses
  root on Unix (line 2257-2266), sets `start_time = time(NULL)`,
  derives `$PGDATA` paths (`postopts_file`, `version_file`, `pid_file`),
  and dispatches via a `switch (ctl_command)` to one of the `do_*` handlers.
- `do_init` — locates `initdb` via `find_other_exec`, builds a command
  string, runs `system(cmd)`. [verified-by-code]
- `do_start` — `read_post_opts`, `start_postmaster`, then optionally
  `wait_for_postmaster_start`. Installs `trap_sigint_during_startup` so
  Ctrl-C during the wait forwards SIGINT to the child postmaster.
  [verified-by-code]
- `do_stop` / `do_restart` — read `pid_file`, send `sig` (set by
  `set_mode` to SIGTERM/SIGINT/SIGQUIT for smart/fast/immediate), then
  poll for `pid_file` deletion or process death.
  [verified-by-code]
- `do_reload` — sends SIGHUP, never waits. [verified-by-code]
- `do_promote` — writes `$PGDATA/promote`, sends SIGUSR1, polls for
  `DBState == DB_IN_PRODUCTION`. Rejects unless current state is
  `DB_IN_ARCHIVE_RECOVERY`. [verified-by-code]
- `do_logrotate` — writes `$PGDATA/logrotate`, sends SIGUSR1.
  [verified-by-code]
- `do_kill(pid)` — for the `kill SIGNALNAME PID` subcommand: sends an
  arbitrary signal to an arbitrary pid (after `set_sig` whitelist:
  HUP/INT/QUIT/ABRT/KILL/TERM/USR1/USR2). [verified-by-code]
- `do_status` — checks pid_file, returns LSB exit code 3 if not running,
  4 if datadir issue. [verified-by-code] [from-comment]
- `start_postmaster` — on Unix, `fork` + `setsid` + `execl /bin/sh -c
  "exec postgres …"`. On Windows, `CreateRestrictedProcess` via `cmd /C`.
  Returns the child PID (or, on Windows, the *shell's* PID since CMD
  has no `exec`). [from-comment]
- `wait_for_postmaster_start(pm_pid, do_checkpoint)` — polls pid_file 10×
  per second up to `wait_seconds` (default 60, overridable via `-t` or
  `$PGCTLTIMEOUT`). Validates `pmstart >= start_time - 2` so it doesn't
  latch onto a stale pid_file from a previous run. Reads
  `LOCK_FILE_LINE_PM_STATUS` (PM_STATUS_READY / PM_STATUS_STANDBY) for
  readiness, or watches child death via `waitpid(... WNOHANG)`. Returns
  `POSTMASTER_READY` / `POSTMASTER_STILL_STARTING` /
  `POSTMASTER_SHUTDOWN_IN_RECOVERY` / `POSTMASTER_FAILED`.
  [verified-by-code]
- `wait_for_postmaster_stop` — polls until pid_file gone, OR `kill(pid, 0)`
  fails. Two-step race protection: if signal probe fails, re-check pid_file
  before declaring uncleanunclean shutdown. [verified-by-code]
- `wait_for_postmaster_promote` — polls until `DBState == DB_IN_PRODUCTION`
  or pid_file vanishes. [verified-by-code]
- `adjust_data_dir` — handles config-only directories: if `pg_data` has
  `postgresql.conf` but no `PG_VERSION`, runs `postgres -C data_directory`
  via `popen` to discover the real PGDATA. [verified-by-code]
- `get_control_dbstate` — wraps `get_controlfile` and bails on bad CRC.
  Used during promote-wait and start-wait. [verified-by-code]
- Windows-only: `pgwin32_doRegister` / `pgwin32_doUnregister` /
  `pgwin32_ServiceHandler` / `pgwin32_ServiceMain` /
  `pgwin32_doRunAsService` / `CreateRestrictedProcess` /
  `GetPrivilegesToDelete`. The restricted-token + job-object sandbox
  preserves `SeLockMemoryPrivilege` (for huge pages) and
  `SeChangeNotifyPrivilege`. [verified-by-code] [from-comment]
- `readfile` / `free_readfile` — slurp-and-split helper for
  `postmaster.pid` and `postmaster.opts`. The whole file is read in one
  syscall to get something close to an atomic snapshot of a concurrently
  written pid_file. [from-comment]

## Notable invariants / details

- Refuses to run as root on Unix (line 2257). On Windows, the restricted
  token strips Administrators and Power Users SIDs from the child.
  [verified-by-code]
- `umask(PG_MODE_MASK_OWNER)` is set early (line 2236), then re-derived
  from the actual PGDATA permissions via `GetDataDirectoryCreatePerm`
  later (line 2467). Order matters because file creation between those
  two umasks would be too-restrictive. [verified-by-code]
- The `setsid()` after `fork()` on Unix (line 477) detaches the postmaster
  from pg_ctl's controlling terminal so that a stray Ctrl-C on the launcher
  doesn't take down the server. [from-comment]
- `PG_GRANDPARENT_PID` is exported so the postmaster's lockfile can refuse
  to overwrite a still-running parent shell (see CreateLockFile comments
  in PG core). [from-comment]
- Shutdown mode → signal: smart→SIGTERM, fast→SIGINT, immediate→SIGQUIT.
  Default is fast. [verified-by-code]
- The pid_file parsing relies on a v10+ format (≥7 lines including
  `LOCK_FILE_LINE_PM_STATUS`). Older pid_files would never advance past
  the `numlines >= LOCK_FILE_LINE_PM_STATUS` check (line 608).
  [verified-by-code]
- The 2-second slop on `pmstart >= start_time - 2` (line 623) is "for
  possible cross-process clock skew" — but in practice both processes
  use the same kernel clock; the slop also covers the case where pg_ctl
  and the forked postmaster cross a `time()`-second boundary.
  [from-comment]
- `trap_sigint_during_startup` (line 858) is set up only AFTER fork so
  there's no chance of forwarding to a yet-unknown postmasterPID. The
  handler clears itself and re-raises so pg_ctl exits with the normal
  signal status. [from-comment]
- Single-user backend detection: a negative PID in pid_file means
  standalone backend; pg_ctl refuses stop/restart/promote/reload in that
  case. [verified-by-code]
- On Windows, the "shell's PID" gotcha means the returned pm_pid is NOT
  comparable to postmaster.pid contents (line 627-629). [from-comment]

## Potential issues

- `pg_ctl.c:104` — `static volatile pid_t postmasterPID = -1;` is
  written by `do_start` BEFORE the signal handler is installed (line 986).
  But `postmasterPID` defaults to -1 and `trap_sigint_during_startup`
  guards with `if (postmasterPID != -1)`, so a SIGINT racing in before
  assignment lands harmlessly. [verified-by-code]
- `pg_ctl.c:498` — `execl("/bin/sh", "/bin/sh", "-c", cmd, ...)` with
  `cmd` containing `exec_path` and `post_opts`. `post_opts` is passed
  through from `-o "..."` user input AND from `postmaster.opts` on
  restart. The opts are double-quoted around `exec_path` but anything
  inside `post_opts` is interpreted by `/bin/sh`. Documented as
  intentional (line 485-488). [ISSUE-security: shell injection via
  postmaster.opts contents (likely if attacker can write to PGDATA)]
- `pg_ctl.c:1056-1077` — `do_stop` waits up to `wait_seconds`, then
  prints a hint suggesting "-m fast" only if currently SMART mode. No
  retry, no escalation; immediate-mode shutdown failure leaves the user
  to invoke kill manually. [verified-by-code]
- `pg_ctl.c:2270` — `wait_seconds = atoi(env_wait)` for `PGCTLTIMEOUT`
  has no validation. Negative or non-numeric values give 0, causing
  immediate timeout. [ISSUE-correctness: PGCTLTIMEOUT unvalidated (nit)]
- `pg_ctl.c:2337` — `wait_seconds = atoi(optarg)` for `-t` same issue.
  [ISSUE-correctness: -t unvalidated (nit)]
- `pg_ctl.c:1334-1342` — `postmaster_is_alive` uses `kill(pid, 0)`; on
  Linux+Solaris this can return 0 for a zombie. Comment notes EPERM is
  treated as "not the postmaster" — but a hostile setuid scenario could
  confuse things. Real risk is low because PGDATA permissions prevent
  cross-user attacks. [from-comment]
- `pg_ctl.c:357-362` — `readfile` re-reads after `fstat` to check the
  file didn't grow; doesn't handle "file shrank" (the comment at line
  329-335 says "close enough for the current use" since pid_file is
  small). [from-comment]
- `pg_ctl.c:1232-1241` — promote: if `kill` fails after writing the
  promote file, the file is `unlink`ed but if that ALSO fails it's just
  logged. Stale promote file then sits until a subsequent successful
  promote consumes it. [verified-by-code] [ISSUE-correctness: stale
  promote signal file on partial failure (nit)]
- `pg_ctl.c:1307-1314` — same pattern for logrotate.
  [ISSUE-correctness: stale logrotate signal file on partial failure (nit)]
- `pg_ctl.c:557-558` (Windows) — `cmd /C` quoting: nested quotes are
  notoriously brittle. The code uses `"%s" /C ""%s" %s%s < "%s" 2>&1"`
  which is per CMD.EXE's docs but any of `exec_path`, `pgdata_opt`,
  `post_opts` containing a `"` could go wrong. No quoting of those.
  [ISSUE-security: Windows command-line injection via post_opts (maybe)]
- `pg_ctl.c:2393` — `killproc = atol(argv[++optind])` for the `kill PID`
  subcommand. No validation; `atol("garbage") = 0`, then `do_kill(0)`
  sends to whole process group. Mitigated by `set_sig` whitelist and the
  user explicitly opting in. [ISSUE-correctness: unvalidated PID (nit)]
- `pg_ctl.c:621-622` — `atol` / `atoll` on pid_file contents. If
  attacker can write pid_file (which they should NOT under PGDATA perms),
  they can mislead pg_ctl. [verified-by-code]
- `pg_ctl.c:1859` (Windows) — `sprintf(jobname, "PostgreSQL_%lu",
  processInfo->dwProcessId)` into 128-byte buffer; the PID is at most
  10 digits, prefix is 11, so safe but `sprintf` is a code-smell. Should
  be `snprintf`. [ISSUE-style: prefer snprintf (nit)]
