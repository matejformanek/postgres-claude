# Issue register — `pgbench`

Covers `src/bin/pgbench/pgbench.c` and `src/bin/pgbench/pgbench.h`.

Sweep A20 bucket D, verified at `e18b0cb7344`.

## Security

- **\shell uses unquoted system(3) / popen(3)** — `pgbench.c:2912-3012`
  (`runShellCommand`). Joins argv with spaces, no quoting. A variable
  containing `;`, `$(…)`, or backticks is interpreted by /bin/sh. By
  design (pgbench scripts are trusted local files) but trivial to
  misuse if combined with `\setshell` whose stdout comes from an
  outside source. (likely)

- **SQL injection via :var substitution is by design** — `pgbench.c:1931`
  (`assignVariables`). No quoting on `:var` substitution into SQL
  strings. Again documented but easy to misuse, especially with
  `\setshell` results assigned to variables that then appear in SQL.
  (likely)

## Correctness

- **chooseScript assumes total_weight > 0** — `pgbench.c:3052-3057`.
  Early-return at line 3049 guards `num_scripts == 1`. With multiple
  scripts and all weights set to 0 by user, `getrand(0, -1)` underflows.
  (nit)

- **`(int) strtol(res, &endptr, 10)` in `runShellCommand`** —
  `pgbench.c:2998`. No range check before the int cast. Shell command
  returning > INT_MAX produces garbage int. (nit)

- **`int64` cast risk in next_report** — `pgbench.c:7669-7677`. Math
  is bounded by user-supplied `progress` arg (seconds); not a practical
  issue. (nit)

- **Three-place change for new failure categories** — `pgbench.c:4585`
  + `accumStats` + `printResults`. Adding a new EStatus failure type
  requires touching three places, easy to miss one. (nit)

## Style / drift

- **8062-line single file** — splitting into multiple compilation units
  would help build times. No movement upstream. (nit)

- **"Horrible hack" comment for thread 0 assumption** — `pgbench.c:7777`.
  Acknowledged by maintainers. Breaks silently if THREAD_CREATE
  semantics change. (nit)

- **ABI-fragile `PgBenchFunction` enum** — `pgbench.h:65-104`. Used as
  a dense index; reordering breaks any vendored consumers. (nit)

- **strtoint64/strtodouble live in pgbench.c but declared in shared
  header** — `pgbench.h:160-161`. Header is shared with exprparse.y;
  putting the number parsers there is a layering smell. (nit)

## Leaks

- **`allocCStatePrepared` allocations freed only at exit** —
  `pgbench.c:3066-3084`. Per-client flag matrix. O(scripts × commands)
  per client; not pathological for benchmark use. (nit)
