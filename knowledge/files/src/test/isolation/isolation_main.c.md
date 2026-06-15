---
path: src/test/isolation/isolation_main.c
anchor_sha: e18b0cb7344
loc: 143
depth: read
---

# src/test/isolation/isolation_main.c

## Purpose

The `main()` for the `pg_isolation_regress` binary — the isolation-test
flavor of the regression driver. Mirrors `pg_regress_main.c` exactly in
shape: supplies `isolation_init` and `isolation_start_test` callbacks
to the shared `regression_main()` in `pg_regress.c`. Each test is a
`.spec` file (a permutation grammar parsed by `specparse.y` inside the
`isolationtester` binary). `isolation_main.c` does NOT itself run the
permutations — it spawns the **isolationtester** child process per
test, which does. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static PID_TYPE isolation_start_test(...)` | `isolation_main.c:28-108` | spawns one `isolationtester < test.spec > test.out` |
| `static void isolation_init(int argc, char **argv)` | `isolation_main.c:110-134` | stashes argv[0], sets default db name |
| `int main(int argc, char *argv[])` | `isolation_main.c:136-143` | trampoline into `regression_main` |

## Internal landmarks

- Default database name: `"isolation_regression"` (`:133`), different
  from pg_regress's `"regression"`.
- `isolationtester` binary path is found lazily via `find_other_exec`
  (`:45-50`) — done on the **first** test spawn, not during init.
  The header comment `:115-123` explains why: `regression_main()`
  calls the init function before parsing `--bindir` and friends, so
  the library search path isn't yet configured; the `-V` probe
  `find_other_exec` does could fail because isolationtester links
  libpq. So this file stashes `argv[0]` during init (`:124`) and runs
  the lookup on first test launch. `[from-comment]`
- The spawned command line (`:83-88`): `isolationtester "dbname=<db>"
  < infile > outfile 2>&1`. No `-X / -a / -q` — those are psql flags.
- `PG_ISOLATION_VERSIONSTR` (`:22`) is the magic string `"isolationtester
  (PostgreSQL) <PG_VERSION>"` that `find_other_exec` compares against.
- File-search dual-path (`:60-73`) — same vpath logic as pg_regress_main.c
  but for `specs/*.spec` instead of `sql/*.sql`.
- Sets `PGAPPNAME=isolation/<testname>` (`:90-92`).

## Invariants & gotchas

- `isolationtester` and `pg_isolation_regress` are TWO separate
  binaries: this file is the runner that launches the former.
- The lazy `find_other_exec` is load-bearing — moving it into
  `isolation_init` will break under `--bindir` overrides.
  `[from-comment]`
- `looked_up_isolation_exec` is a one-shot guard — the lookup happens
  once per process, not once per test.
- `postfunc=NULL` (`:142`) — no per-result postprocessing for
  isolation tests.

## Cross-refs

- `knowledge/files/src/test/isolation/isolationtester.c.md` — the
  permutation engine.
- `knowledge/files/src/test/isolation/isolationtester.h.md` — the
  `Step` / `Session` / `Permutation` / `TestSpec` structs.
- `knowledge/files/src/test/regress/pg_regress.c.md` — the shared
  driver.
- `knowledge/files/src/test/regress/pg_regress_main.c.md` — sibling
  psql-flavor.
