---
path: src/test/regress/pg_regress.c
anchor_sha: e18b0cb7344
loc: 2744
depth: read
---

# src/test/regress/pg_regress.c

## Purpose

The regression-test driver — the **core of `pg_regress` and
`pg_isolation_regress`**. Started life as a C translation of an
older shell script (Magnus Hagander, `[from-comment]` at `:5-7`). It
runs the entire in-tree regression suite end-to-end:

1. parses command-line flags (port, bindir, schedule, temp-instance,
   etc.),
2. optionally builds and starts a **throw-away postgres temp
   instance** (initdb + pg_ctl start + CREATE ROLE / DATABASE),
3. walks one or more **schedule files** describing parallel test
   groups,
4. spawns a test binary per `.sql` (psql) or `.spec` (isolationtester)
   case via the flavor-specific `startfunc`,
5. waits, diffs each result against the `expected/` baseline, and
6. emits **TAP protocol** output for meson / prove harnesses.

The single entry point `regression_main()` (`:2140`) is shared by
both `pg_regress` (psql) and `pg_isolation_regress` (isolationtester)
binaries via the callbacks declared in `pg_regress.h`. This is the
LOAD-BEARING test driver — without it `meson test`'s regression
target produces nothing. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int regression_main(argc, argv, ifunc, startfunc, postfunc)` | `:2140` | the actual driver |
| `void add_stringlist_item(_stringlist **listhead, const char *str)` | `:202` | append helper |
| `PID_TYPE spawn_process(const char *cmdline)` | `:1215` | fork+exec / CreateRestrictedProcess |
| `bool file_exists(const char *file)` | `:1318` | stat() wrapper |
| globals: `host_platform`, `basic_diff_opts`, `pretty_diff_opts`, `dblist`, `debug`, `inputdir`, `outputdir`, `expecteddir`, `bindir`, `launcher` | `:52-105` | configurable knobs (most set from CLI) |

## Internal landmarks

### Setup & cleanup

- `unlimit_core_size()` (`:178`) — raises `RLIMIT_CORE` to its hard
  limit so core dumps from crashed test backends are captured.
- `make_temp_sockdir()` (`:511`) — creates `/tmp/pg_regress-XXXXXX`
  with `mkdtemp`, registers `remove_temp` via `atexit` + signal
  handlers (`:526-539`). Comment explains: socket paths are typically
  constrained well below `_POSIX_PATH_MAX`, so we put the dir under
  `/tmp` rather than relative to a deep CWD. `[from-comment]`
- `remove_temp()` (`:478`) — `unlink(sockself)`, `unlink(socklock)`,
  `rmdir(temp_sockdir)`. Designed to be signal-handler-safe on Unix
  (NOT on Windows — but pg_regress on Windows defaults to TCP, not
  Unix sockets). `[from-comment]`
- `stop_postmaster()` (`:443`) — `atexit` hook that calls
  `pg_ctl stop` on the temp instance.
- `initialize_environment()` (`:733`) — scrubs `PGCHANNELBINDING`,
  `PGCONNECT_TIMEOUT`, `PGDATABASE`, etc. (`:828-854` — keep in sync
  with `PostgreSQL/Test/Utils.pm` per the comment at `:826`), sets
  `PGTZ=America/Los_Angeles` (`:796`), `PGDATESTYLE='Postgres, MDY'`
  (`:797`), `PGOPTIONS='-c intervalstyle=postgres_verbose'`
  (`:805-815`). These are the well-known regression-test environment
  invariants that make `select now()` style tests reproducible.

### Temp instance bring-up (`:2362-2620`-ish, inside `regression_main`)

- Port chosen if not specified: `0xC000 | (PG_VERSION_NUM & 0x3FFF)`
  (`:2344`) — falls in the IANA private range 49152-65535, derived
  from the version number so parallel branches don't collide.
  `[from-comment]`
- `initdb` invocation: either runs a real `initdb` (`:2412-2431`) or,
  if `INITDB_TEMPLATE` env is set and no `--no-locale` / `--debug` /
  `PG_TEST_INITDB_EXTRA_OPTS`, copies a pre-built template directory
  (`cp -RPp` on Unix, `robocopy` on Windows, `:2435-2459`). The
  template path is set up by the meson build for speed. `[from-comment]`
- `pg_ctl start` and a polling `PQping` loop wait until the
  postmaster accepts connections.
- `CREATE DATABASE` per `dblist`, `CREATE ROLE` per `--create-role`,
  optional `LOAD '<extension>'` per `--load-extension`.

### Schedule processing

- `run_schedule()` (`:1714`) — the heart of parallel test
  orchestration:
  - opens the schedule file (`scf = fopen(schedule, "r")`, `:1735`),
  - reads each non-blank, non-`#` line,
  - expects every line to start with `"test: "` (`:1756`) — anything
    else is a syntax error,
  - splits the rest on whitespace into 1..N test names,
  - if N == 1: spawn + wait sequentially,
  - if N > 1: spawn all in parallel, `wait_for_tests` blocks until
    all complete (`:1842-1849`),
  - if `--max-connections` is set and N > max: chunk into groups of
    `max_connections` (`:1816-1838`),
  - if `--max-concurrent-tests` is set and N > max: hard error
    (`:1811-1815`),
  - cap at `MAX_PARALLEL_TESTS = 100` per line (`:1717`).
- `run_single_test()` (`:1920`) — bypass schedule, run one ad-hoc
  test name on the CLI.
- `wait_for_tests()` (`:1624`) — `waitpid` loop on Unix /
  `WaitForMultipleObjects` on Windows.

### Diff machinery

- `results_differ()` (`:1417`) — drives `diff(1)`:
  - first tries `expected/<test>.out` (or platform-specific via
    `resultmap`, see below),
  - if no match, tries alternative files `<test>_1.out` ..
    `<test>_9.out` (`:1469-1502`) — the **alternative-expected
    mechanism** for tests that legitimately have multiple acceptable
    outputs (collation differences, error wording variations),
  - picks the alternative with the fewest diff lines as the "best
    match" (`:1494-1499`) and prints a **pretty diff** (with `-U3`
    context, `:65`) to the combined `regression.diffs` file,
  - caps emitted diff to 80 lines per test (`:1574`) to avoid
    flooding output when a crash causes every downstream test to
    fail. `[from-comment]`
- `run_diff()` (`:1386`) — wraps `system(cmd)`, checks exit code.
- Diff options: `basic_diff_opts` = `""` (Unix) or `"--strip-trailing-cr"`
  (Windows); `pretty_diff_opts` = `"-U3"` or `"--strip-trailing-cr -U3"`
  (`:64-69`).

### Platform-specific expected files: resultmap

- `load_resultmap()` (`:630`) — reads `inputdir/resultmap`, a file
  with lines `testname:filetype:platform_pattern=expectedfile`.
  Each matching line for the current `host_platform` (compiled-in
  HOST_TUPLE, `:52`) prepends an entry to the `resultmap` linked
  list. Last match wins because we always prepend. `[from-comment]`
- `get_expectfile()` (`:705`) — given testname + filename, returns
  the platform-specific expected-file basename or NULL.
- `string_matches_pattern()` (`:557`) — minimal regex (only `.` and
  `.*`) used to match `host_platform` against pattern. Comment notes
  this could be extended if needed. `[from-comment]`

### TAP output

- `enum TAPtype` (`:84-96`): `DIAG`, `DIAG_DETAIL`, `DIAG_END`,
  `BAIL`, `NOTE`, `NOTE_DETAIL`, `NOTE_END`, `TEST_STATUS`, `PLAN`,
  `NONE`.
- `emit_tap_output_v()` (`:346`) — single funnel:
  - `DIAG*` and `BAIL` go to stderr, everything else to stdout
    (`:364-367`),
  - `NOTE` / `DIAG` / `BAIL` lines are prefixed with `# ` per TAP
    convention (`:396-398`),
  - mirrors all output to `logfile` if open,
  - saves/restores `errno` around `vfprintf` calls because `%m`
    placeholders need it intact (`:357`, `:400`). `[from-comment]`
- Convenience macros (`:164-172`): `plan(x)`, `note(...)`,
  `diag(...)`, `note_detail(...)`, `diag_detail(...)`,
  `note_end()`, `diag_end()`, `bail(...)`, `bail_noatexit(...)`.
- `test_status_print()` (`:285`) — prints `ok 1 - testname  123 ms`
  (parallel test → `+ testname`, sequential → `- testname`) at
  fixed column widths (`TESTNAME_WIDTH = 36`, `:76`) so output
  aligns vertically.

### psql command construction (helpers consumed by callers)

- `psql_start_command()` (`:1131`) → returns a `StringInfo` opened
  with the psql prefix.
- `psql_add_command()` (`:1143`) → append a SQL command.
- `psql_end_command()` (`:1180`) → append the DB name and `system()`-
  execute the assembled command; `bail()` on failure.
- `psql_command(database, ...)` macro (`:1202-1207`) — start/add/end
  in one call.

### Process spawning

- `spawn_process()` (`:1215`) — Unix path forks + `execl(shellprog,
  "-c", "exec <cmdline>")` (`:1246`); the explicit `exec` saves two
  useless intermediate processes per parallel test. `[from-comment]`
  Windows path uses `CreateRestrictedProcess` (`:1265`).
- `EXEC_BACKEND` path calls `pg_disable_aslr()` before fork
  (`:1226`).

### CLI flags (long-options table at `:2145-2171`)

`--help`, `--version`, `--dbname`, `--debug`, `--inputdir`,
`--max-connections`, `--encoding`, `--outputdir`, `--schedule`,
`--temp-instance`, `--no-locale`, `--host`, `--port`, `--user`,
`--bindir`, `--dlpath`, `--create-role`, `--temp-config`,
`--use-existing`, `--launcher`, `--load-extension`, `--config-auth`,
`--max-concurrent-tests`, `--expecteddir`.

`--bindir=` with empty value means "use `PATH`" (`:2266-2271`).
`--temp-instance` triggers initdb + start of an isolated cluster.

## Invariants & gotchas

- **Schedule file syntax** is rigid: every non-blank, non-`#` line
  MUST begin with literal `"test: "` followed by 1..100 whitespace-
  separated test names. Any other prefix is a fatal syntax error
  (`:1760`). Older PG syntax supported `ignore:`; this driver does
  not.
- Single test name on a line = sequential. Multiple = parallel
  group, all started together, joined before the next line.
- **`MAX_PARALLEL_TESTS = 100`** (`:1717`) is a hard cap per
  schedule line. Sounds high but is reachable for `parallel_schedule`'s
  largest group.
- The default port is **PG_VERSION-derived** (`0xC000 | (PG_VERSION_NUM
  & 0x3FFF)`) to avoid clashing with parallel branches.
- Resultmap **last match wins** because entries are prepended to the
  linked list — this mirrors the original shell script's behavior.
  `[from-comment]`
- The temp-instance socket directory is `/tmp/pg_regress-XXXXXX`
  with mode 0700 — comment explains the security reasoning: a wider
  permission would let other OS users connect to the trust-auth'd
  postmaster. `[from-comment]` at `:500-510`.
- TAP output: diagnostics MUST go to stderr (under prove's default
  config, stdout `# `-prefixed lines are visible but stderr is too;
  pg_regress sends `DIAG_*` and `BAIL` to stderr deliberately, see
  `:362-367`). `[from-comment]`
- `errno` save/restore wrapper around `vfprintf` (`:357-400`) is
  load-bearing for `%m` to work — never remove without auditing all
  callers.
- `--launcher` (`:104`, used in `psql_cmd` construction by callers)
  is the documented hook for valgrind / strace / leak-checker
  wrappers around each test process. Setting it to
  `"valgrind --leak-check=full"` is the standard way to leak-check
  the regression suite.
- On Windows, `remove_temp()` MUST NOT be called from a signal
  handler (`:474-477`) — but Windows pg_regress defaults to TCP,
  not Unix sockets, so the signal handler isn't installed.
  `[from-comment]`
- `INITDB_TEMPLATE` env var: the meson build sets this to a
  pre-initdb'd directory so subsequent runs skip the slow initdb.
  Falls back to a real initdb if `--no-locale`, `--debug`, or
  `PG_TEST_INITDB_EXTRA_OPTS` are present (these would change the
  resulting cluster). `[from-comment]` at `:2401-2410`.
- Comment at `:2404-2406` notes that there's nearly-identical code
  in `Cluster.pm`, but they can't be deduplicated until perl is
  required at build time. `[from-comment]`

## Cross-refs

- `knowledge/files/src/test/regress/pg_regress.h.md` — the shared API.
- `knowledge/files/src/test/regress/pg_regress_main.c.md` — psql flavor.
- `knowledge/files/src/test/isolation/isolation_main.c.md` — isolation
  flavor.
- `knowledge/files/src/test/regress/regress.c.md` — the C extension
  loaded by the SQL tests.
- `knowledge/subsystems/testing.md` (if present) — regression vs TAP vs
  isolation overview.
- `src/test/regress/parallel_schedule` — the main schedule file
  consumed.
- `src/test/regress/resultmap` — platform overrides consumed by
  `load_resultmap`.
