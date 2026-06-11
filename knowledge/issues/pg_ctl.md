# Issue register — `pg_ctl`

Covers `src/bin/pg_ctl/pg_ctl.c` (the postmaster front-end).

Sweep A20 bucket D, verified at `e18b0cb7344`.

## Security

- **Shell injection via postmaster.opts content** — `pg_ctl.c:498`.
  `execl("/bin/sh", "-c", cmd, ...)` where `cmd` embeds `post_opts`
  read from `$PGDATA/postmaster.opts` on restart, or from user `-o`
  on start. An attacker who can write to `postmaster.opts` (which is
  inside PGDATA, so they should not be able to without already
  controlling the cluster) can execute arbitrary shell. (likely if
  PGDATA perms are loose)

- **Windows command-line nested-quote brittleness** — `pg_ctl.c:557-561`.
  `cmd /C ""%s" %s%s < "%s" 2>&1"`. `exec_path` / `pgdata_opt` /
  `post_opts` are interpolated into a CMD.EXE command line with no
  quoting of embedded `"`. (maybe)

## Correctness

- **PGCTLTIMEOUT unvalidated** — `pg_ctl.c:2270`. `atoi(env)` accepts
  negative/garbage values. Negative produces 0 timeout. (nit)

- **`-t` unvalidated** — `pg_ctl.c:2337`. Same issue. (nit)

- **`kill PID` accepts garbage PID** — `pg_ctl.c:2393`.
  `killproc = atol(argv[++optind])`; `atol("garbage") = 0`, then
  `do_kill(0)` signals the whole process group. (nit)

- **Stale promote signal file on partial failure** — `pg_ctl.c:1232-1241`.
  If `kill` fails after writing promote file, we attempt to `unlink` it
  and if that fails too we just log. (nit)

- **Stale logrotate signal file on partial failure** — `pg_ctl.c:1307-1314`.
  Same pattern as promote. (nit)

- **`do_stop` no shutdown-mode escalation** — `pg_ctl.c:1056-1077`.
  After timeout, prints a hint to use `-m fast` only if currently smart;
  no automatic escalation. (nit)

- **`postmaster_is_alive` accepts zombies on some Unixes** —
  `pg_ctl.c:1334-1342`. `kill(pid, 0) == 0` returns success even for
  zombie. Race window: postmaster reaped between our check and our
  signal send. (nit)

- **`readfile` doesn't handle file shrinking** — `pg_ctl.c:357-362`.
  Re-checks size grew (returns NULL) but not "smaller than fstat said".
  Acceptable per comment. (nit)

- **`sprintf` rather than `snprintf` in Windows path** —
  `pg_ctl.c:1859`. `sprintf(jobname, "PostgreSQL_%lu", pid)`. Buffer
  safe by arithmetic but style-bad. (nit)

## Race conditions / signal handling

- **`postmasterPID` write before signal handler install** —
  `pg_ctl.c:986`. Default -1 + guard in handler makes the race
  harmless. (verified-by-code; documenting for next reviewer)

- **2-second slop on pid_file validation** — `pg_ctl.c:623`. Cross-process
  clock skew accommodation; same kernel clock, slop also covers second
  boundary cross. (from-comment; documented as intentional)

## Style / docs

- **Hint only fires for smart shutdown** — `pg_ctl.c:1069-1071`.
  If user is in immediate mode and that fails, they get no helpful
  message at all. (nit)
