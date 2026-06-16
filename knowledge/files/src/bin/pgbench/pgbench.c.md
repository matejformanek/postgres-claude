# `src/bin/pgbench/pgbench.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~8062
- **Source:** `source/src/bin/pgbench/pgbench.c`

PostgreSQL's load-test workhorse. Implements the TPC-B-style benchmark
("tpcb-like" / "simple-update" / "select-only" builtin scripts plus
user-supplied scripts), a tiny expression language with variables,
control flow (\if / \elif / \else / \endif), pipelining (\startpipeline
/ \syncpipeline / \endpipeline), per-script weighting, multi-threaded
clients with their own state machines, throughput throttling, latency
limit + retry-on-deadlock/serialization, per-script and per-command
statistics, and three query modes (simple / extended / prepared).
Originally written by Tatsuo Ishii (2000); the largest single-file
front-end in src/bin. [from-comment]

## Architecture in one paragraph

Each thread (`TState`) drives `nstate` clients (`CState`). A connection
goes through a per-client state machine (`ConnectionStateEnum`):
CSTATE_CHOOSE_SCRIPT → optionally CSTATE_PREPARE_THROTTLE/_THROTTLE →
CSTATE_START_TX → loop over (CSTATE_START_COMMAND → CSTATE_WAIT_RESULT
| CSTATE_SLEEP → CSTATE_END_COMMAND), with detours through CSTATE_ERROR
→ CSTATE_WAIT_ROLLBACK_RESULT → CSTATE_RETRY or CSTATE_FAILURE. The
main thread loop (`threadRun`) builds a `socket_set` (ppoll or select)
for clients in CSTATE_WAIT_RESULT, computes the nearest wakeup
(throttle delay / sleep deadline / next progress report), waits, then
calls `advanceConnectionState` on each newly-ready client. Stats are
accumulated in `StatsData` per script and per thread, merged at the end.

## API / entry points

The file is enormous. Key functions, grouped:

- **main loop**
  - `main(argc, argv)` (line 6731) — argv parsing (huge getopt),
    builtin or file scripts, `find_other_exec` for psql utilities,
    `THREAD_BARRIER_INIT`, spawn threads, `THREAD_JOIN`, merge stats,
    `printResults`.
  - `threadRun(arg)` (line 7531) — per-thread main loop, opens
    log file, opens client connections (unless `--connect`), barrier
    "READY", barrier "GO", then the `while (remains > 0)` loop.
  - `advanceConnectionState(thread, st, agg)` (line 3668) — the
    state-machine dispatcher; long function. [verified-by-code]
  - `executeMetaCommand(st, now)` (line 4366) — \set / \shell /
    \sleep / pipeline / conditional dispatch.
- **expression eval**
  - `evaluateExpr(st, expr, retval)` (line 2827).
  - `evalFunc` / `evalLazyFunc` / `evalStandardFunc` for the
    `PgBenchFunction` cases. PERMUTE uses Murmur-style hashing
    (`permute`, line 1294). [from-comment]
  - `getrand` / `getExponentialRand` / `getGaussianRand` /
    `getPoissonRand` / `getZipfianRand` / `computeIterativeZipfian`
    (lines 1093-1234). Each takes a separate `pg_prng_state` so threads
    don't share PRNG state. [verified-by-code]
- **scripts and parsing**
  - `ParseScript(script, desc, weight)` (line 5999) — splits a script
    into Command[] using `psql_scan` + `process_backslash_command` for
    metacommands.
  - `process_backslash_command(state, source, ...)` (line 5738) —
    consumes one `\…` command. Special-cased: `\set` reparses with
    `expr_yyparse`; `\if` arg likewise.
  - `findBuiltin(name)` / `parseScriptWeight(option, &script)` /
    `addScript(script)` — script registry. [verified-by-code]
  - `CheckConditional(ps)` (line 5949) — static validation that \if /
    \endif balance.
- **table init**
  - `runInitSteps(initialize_steps)` (line 5326) — interprets the
    `-I dtgGvpf` letters as drop/createTables/clientGen/serverGen/vacuum/
    primaryKeys/foreignKeys.
  - `initGenerateDataClientSide` (line 5152) — `COPY pgbench_accounts
    FROM STDIN` with client-side row generation; the inner
    `initPopulateTable` writes formatted rows via PQputCopyData.
  - `initGenerateDataServerSide` (line 5184) — `INSERT INTO ... SELECT
    generate_series(...)`, much faster but only via server CPU.
- **stats**
  - `processXactStats(thread, st, now, skipped, agg)` (line 4753).
  - `accumStats(stats, skipped, lat, lag, estatus)` (line 1443) —
    accumulator. EStatus mapped to `cnt` / `skipped` / failure counters.
  - `printResults(total, ...)` (line 6452) — final report.
- **logging**
  - `doLog(thread, st, agg, skipped, latency, lag)` (line 4630) —
    per-tx log row OR per-interval aggregate row (`--aggregate-interval`).
- **alarm/signal**
  - `handle_sig_alarm(SIGNAL_ARGS)` (line 7847) — sets `timer_exceeded`.
  - `setalarm(seconds)` (line 7853) — `pqsignal(SIGALRM, ...)` +
    `alarm()`. On Windows uses a thread + Sleep.
- **socket polling**
  - `alloc_socket_set` / `wait_on_socket_set` — wrappers around either
    `ppoll` or `select` per build-time toggle (lines 46-115).

## Notable invariants / details

- `MAX_SCRIPTS = 128` (line 349) — hard cap on number of `-f` /
  `-b` scripts. [verified-by-code]
- `MAX_ARGS = 256` (line 694) — per Command argv length cap. Affects
  both metacommand args and SQL variable substitutions.
- `SHELL_COMMAND_SIZE = 256` (line 350) — total bytes available to a
  `\shell` / `\setshell` invocation after variable expansion.
- `THREAD_BARRIER_T` is `pthread_barrier_t` on POSIX and
  `SYNCHRONIZATION_BARRIER` on Windows. Two barriers in
  threadRun: "READY" (after log open) and "GO" (after pre-warm
  connections). [verified-by-code]
- `is_connect` mode (one PGconn per tx) reconnects in CSTATE_START_TX
  and skips the pre-warm loop. [from-comment]
- The "epoch_shift" global converts `pg_time_usec_t` (relative) into
  Unix-epoch absolute timestamps for log output (line 7604 rounds
  down to second boundary). [from-comment]
- Per-PRNG state separation:
  - `base_random_sequence` (initialized from `--random-seed`).
  - `TState`'s `ts_choose_rs` / `ts_throttle_rs` / `ts_sample_rs`.
  - `CState`'s `cs_func_rs` (for script functions) and
    `random_state` (so retries reproduce). [verified-by-code]
- `runShellCommand` (line 2912) joins argv into a single command and
  passes it to `system()` or `popen()` — see security caveat below.
- `process_backslash_command` accepts/rejects meta-commands per
  `getMetaCommand` (line 2870) — note `\copyfreq` and similar are NOT
  in the list; only the ones at lines 696-712 are valid.
- The script weights are stored in `total_weight` (int64) and accessed
  via `chooseScript` using `getrand(thread, 0, total_weight - 1)` and
  cumulative subtraction (line 3052-3057).
- `executeMetaCommand` handles `\sleep` by setting `st->sleep_until =
  now + microseconds` and returning CSTATE_SLEEP. The polling loop in
  `threadRun` wakes up at `sleep_until`. [verified-by-code]
- `getQueryParams` (line 1967) extracts $1..$n positional parameters
  for QUERY_EXTENDED / QUERY_PREPARED modes.
- `assignVariables(variables, sql)` (line 1931) substitutes `:varname`
  in the SQL string by mutating it in place. Called for QUERY_SIMPLE.
  Used to allocate a new string; now reallocs the SQL buffer.
  [verified-by-code]
- Conditional stack (`fe_utils/conditional.h`) for nested \if/\elif/
  \else/\endif. CSTATE_SKIP_COMMAND fast-skips commands inside
  not-taken branches. [verified-by-code]

## Potential issues — pgbench-specific footguns

- `pgbench.c:1931-1965` (`assignVariables`) — Variables in SQL are
  substituted with raw string values from `:var`. There is NO quoting
  or escaping. A `\set q 'DROP TABLE x'` followed by
  `SELECT :q;` injects SQL. This is intentional — pgbench scripts are
  trusted local files — but it means that scripts taking input from
  the shell (`\setshell`) become SQL-injection vectors if the shell
  command reads attacker-controlled data.
  [ISSUE-security: SQL injection via :variable substitution is by
  design and documented but easy to misuse (likely)]
- `pgbench.c:2912-3012` (`runShellCommand`) — `\shell` and `\setshell`
  pass their joined-with-spaces command to `system(3)` or `popen(3)`,
  which goes through /bin/sh. There is no quoting between arguments.
  A variable containing `;` or `$(…)` lets that shell metacharacter
  through. Again: trusted scripts, but combining with `\setshell`
  results read from the shell is dangerous.
  [ISSUE-security: \shell uses system() with no quoting (likely)]
- `pgbench.c:2914` — `command[SHELL_COMMAND_SIZE = 256]` is a fixed
  stack buffer. The size check at line 2950 prevents overflow but the
  256-byte limit is very small for real-world commands; "shell command
  is too long" is the error.
  [verified-by-code]
- `pgbench.c:2998` — `(int) strtol(res, &endptr, 10)` truncates to int;
  a value > INT_MAX from the shell becomes garbage. No range check on
  the `int` cast. [ISSUE-correctness: int cast of strtol without
  range check (nit)]
- `pgbench.c:7549-7554` — log filename is `prefix.PID[.tid]` where
  `prefix` comes from `--log-prefix=...` (user). No quoting / no path
  validation. A prefix containing `/` opens files anywhere the user has
  write access. Working as designed but easy to mis-set.
  [verified-by-code]
- `pgbench.c:7558-7559` — `fopen` failure at log open is `pg_fatal`,
  which short-circuits other threads still spinning up. Race window
  is small but observable: clean partial-startup is undefined.
  [verified-by-code]
- `pgbench.c:4753` (`processXactStats`) and stat counters — per-tx
  stats are computed in microseconds (`pg_time_usec_t = int64`). 584
  years of headroom but the per-thread `latency.sum2` uses `double` and
  can lose precision under extreme volume.
  [from-comment]
- `pgbench.c:7669-7677` — progress wake-up math: `(int64) 1000000 *
  progress` for `next_report`. With `progress` as an `int` and large
  values (~2000 s) overflow is around 2^31 us = 35 minutes; user-facing
  progress arg is "seconds between reports", normally small. Not a
  practical concern. [verified-by-code]
- `pgbench.c:4366` (`executeMetaCommand`) — \sleep argument values
  read via `evaluateSleep` (line 3433); if the result is negative the
  function clamps to 0 (or returns false), so `\sleep -5 s` does not
  produce a backward time. [verified-by-code]
- `pgbench.c:3052-3057` — `chooseScript` loops `do { w -= weight }
  while (w >= 0)` and returns `i - 1`. If `total_weight` is 0 this
  divides nothing but the function path is guarded by
  `num_scripts == 1` early-return (line 3049). Still, `total_weight ==
  0` with `num_scripts > 1` would underflow `getrand(0, -1)`.
  [ISSUE-correctness: chooseScript assumes total_weight > 0 (nit)]
- `pgbench.c:3066-3084` (`allocCStatePrepared`) — palloc'd per-client
  flag array; freed at process exit only. Per-client allocation O(scripts
  × commands) — for huge scripts this can add up but not pathological.
  [verified-by-code]
- `pgbench.c:1599-1657` (`lookupVariable` / `getVariable`) — variables
  are stored in a per-client sorted array `Variables.vars`; lookup is
  bsearch when `vars_sorted`, linear when newly mutated. Insert sets
  `vars_sorted = false` and a later lookup triggers `qsort`. Behaviour
  is correct but the bookkeeping is easy to break when adding new
  insertion sites. [verified-by-code]
- `pgbench.c:4585-4595` (`getFailures`) — sums
  `serialization_failures + deadlock_failures + other_sql_failures`;
  any new failure category must be added here, in
  `accumStats`, and in `printResults`. Three-place change.
  [ISSUE-doc-drift: triple-source for failure categories (nit)]
- `pgbench.c:6731` (`main`) — `--max-tries`, `--latency-limit`, and
  `-T duration` interact in subtle ways for retries. Their combination
  is described at the top of the file (lines 273-284) but the actual
  enforcement is scattered across `advanceConnectionState`, `doRetry`,
  and `processXactStats`. [from-comment]
- `pgbench.c:7689-7701` — when `min_usec == PG_INT64_MAX` (no client
  has any wakeup) AND `nsocks == 0` we'd be about to sleep forever; the
  code takes the `wait_on_socket_set(sockets, 0)` path which is
  "no timeout". Looks fine but the `else` branch comment is
  misleading. [ISSUE-style: comment says "no explicit delay, wait
  without timeout" but the inner usleep path would also fit (nit)]
- `pgbench.c:7777-7783` (`threadRun`) — "Horrible hack" comment
  acknowledges that the thread pointer for thread 0 must equal
  `threads[0]` because `printProgressReport` indexes into the threads
  array. If `THREAD_CREATE` were ever changed to pass copies, this
  breaks silently. [from-comment]
- `pgbench.c:5326-5410` (`runInitSteps`) — sequencing of -I letters
  is positional; `f` (foreign keys) before `g` (generate data) creates
  the FKs before there are tuples, which postgres tolerates but may
  surprise users. [verified-by-code]
- `pgbench.c:5520-5579` (`parseQuery`) — finds `:varname` substitutions
  in SQL for QUERY_EXTENDED. Variable names must satisfy
  `valid_variable_name` (line 1733): `[A-Za-z_][A-Za-z_0-9]*`.
  [verified-by-code]
- `pgbench.c:8062` end — the file is approaching the size where
  splitting `pgbench.c` into multiple compilation units would help
  build times. No movement upstream toward that yet.
  [ISSUE-style: 8062-line single file (nit)]

## Cross-references

- `pgbench.h` — shared types with `exprparse.y` / `exprscan.l`.
- `fe_utils/psqlscan.c` — the lexer pgbench reuses for SQL splitting.
- `fe_utils/conditional.c` — conditional-stack used by \if.
- `fe_utils/cancel.c` — Ctrl-C handler.
- `common/pg_prng.c` — PRNG implementations behind getrand and friends.

<!-- issues:auto:begin -->
- [Issue register — `pgbench`](../../../../issues/pgbench.md)
<!-- issues:auto:end -->
