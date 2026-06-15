---
path: src/test/regress/pg_regress_main.c
anchor_sha: e18b0cb7344
loc: 117
depth: read
---

# src/test/regress/pg_regress_main.c

## Purpose

The `main()` for the standard regression-test binary `pg_regress`. It is
the **psql-flavor** of the driver: each test is one `.sql` script run
through `psql`, the resulting `.out` is diff'd against `expected/*.out`.
This file supplies two callbacks — `psql_init` and `psql_start_test` —
to the shared driver `regression_main()` in `pg_regress.c`. The bulk of
the work (option parsing, schedule walking, parallel execution, diff,
TAP reporting) lives in the shared driver. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static PID_TYPE psql_start_test(testname, resultfiles, expectfiles, tags)` | `pg_regress_main.c:28-101` | spawns one `psql <test.sql > test.out` |
| `static void psql_init(int argc, char **argv)` | `pg_regress_main.c:103-108` | sets default db name `"regression"` |
| `int main(int argc, char *argv[])` | `pg_regress_main.c:110-117` | trampolines into `regression_main` with the two callbacks |

## Internal landmarks

- Default database name `"regression"` is added at `:107` via
  `add_stringlist_item(&dblist, "regression")`. `--dbname=` on the
  command line can override.
- `psql_start_test` (`:28`) builds the psql command line:
  `psql -X -a -q -d "<dbname>" -v HIDE_TABLEAM=on -v HIDE_TOAST_COMPRESSION=on
   < infile > outfile 2>&1` (`:74-81`).
  - `-X` skips `~/.psqlrc`.
  - `-a` echoes all input.
  - `-q` quiets startup banner.
  - `HIDE_TABLEAM=on` suppresses table-AM info so tests are AM-agnostic.
    `[from-comment]` at `:71-73`.
  - `HIDE_TOAST_COMPRESSION=on` masks TOAST compression info.
- vpath search logic at `:42-60`: looks in `outputdir/sql/<name>.sql`
  first (for builds outside the source tree), falls back to
  `inputdir/sql/<name>.sql`. Same dual-search for `expected/*.out`.
  `[from-comment]`
- Sets `PGAPPNAME=pg_regress/<testname>` (`:83-85`) so the running test
  is identifiable in `pg_stat_activity` / server logs; unsets after
  spawn.
- `INVALID_PID` from `spawn_process` causes `exit(2)`.
- `postfunc` argument is `NULL` (`:116`) — psql output needs no
  per-result postprocessing.

## Invariants & gotchas

- This file is intentionally tiny — all the heavy lifting (signal
  handling, temp-instance setup, schedule parsing, parallel-group
  execution, diff invocation, TAP emission) lives in `pg_regress.c`
  behind `regression_main()`.
- If you need to change psql's invocation flags (e.g. add `-1` for
  single-transaction mode), edit `:74-81` here, NOT pg_regress.c.
- The `dblist` is comma-split inside `regression_main()` if `--dbname`
  passes multiple names; `psql_init` only seeds the default.

## Cross-refs

- `knowledge/files/src/test/regress/pg_regress.c.md` — the driver.
- `knowledge/files/src/test/regress/pg_regress.h.md` — shared API.
- `knowledge/files/src/test/isolation/isolation_main.c.md` — the
  isolationtester-flavor analog.
