---
path: src/test/regress/pg_regress.h
anchor_sha: e18b0cb7344
loc: 67
depth: read
---

# src/test/regress/pg_regress.h

## Purpose

Public API of the regression-test driver shared by `pg_regress` (the
postgres-flavor) and `pg_isolation_regress` (the isolation-flavor).
Declares the `regression_main()` entry point that both binaries call,
the callback signatures each binary supplies (`init_function`,
`test_start_function`, `postprocess_result_function`), and the global
configuration variables (`bindir`, `dblist`, `inputdir`, `outputdir`,
`expecteddir`, `launcher`, `debug`, plus diff-option strings) the
driver expects its callers to read and the binaries to consume.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `typedef struct _stringlist` | `pg_regress.h:22-26` | linked list of strings, used for db list, schedule list, etc. |
| `typedef void (*init_function)(int argc, char **argv)` | `pg_regress.h:33` | called before getopt parsing |
| `typedef PID_TYPE (*test_start_function)(testname, resultfiles, expectfiles, tags)` | `pg_regress.h:36-39` | spawns one test |
| `typedef void (*postprocess_result_function)(const char *filename)` | `pg_regress.h:42` | optional per-result hook |
| `int regression_main(argc, argv, ifunc, startfunc, postfunc)` | `pg_regress.h:60-63` | driver entry |
| `void add_stringlist_item(_stringlist **listhead, const char *str)` | `pg_regress.h:65` | append to list |
| `PID_TYPE spawn_process(const char *cmdline)` | `pg_regress.h:66` | fork+exec or Windows CreateProcess |
| `bool file_exists(const char *file)` | `pg_regress.h:67` | stat() wrapper |
| extern globals | `pg_regress.h:45-58` | `bindir`, `libdir`, `datadir`, `host_platform`, `dblist`, `debug`, `inputdir`, `outputdir`, `expecteddir`, `launcher`, `basic_diff_opts`, `pretty_diff_opts` |

## Internal landmarks

- `PID_TYPE` macro abstracts pid_t / HANDLE across Unix and Windows
  (`:13-19`), with `INVALID_PID` constant for sentinel comparisons.
- The three callback typedefs (`init_function`, `test_start_function`,
  `postprocess_result_function`) form the strategy hooks that let
  `pg_regress_main.c` (psql-driven) and `isolation_main.c`
  (isolationtester-driven) share `regression_main`.

## Invariants & gotchas

- The header includes `<unistd.h>` (`:11`) unconditionally — relies on
  Windows builds providing the win32 shim. See
  `knowledge/files/src/include/port/win32_msvc/unistd.h.md`.
- `_stringlist` order matters when it's a schedule list (parallel
  groups are read in order) but NOT when it's a db list (just
  iterated for connection).
- `tags` parameter on `test_start_function` lets a test annotate its
  result file with a tag for the failure summary; isolation tests use
  this less, regress tests use it for the alternative-output mechanism.

## Cross-refs

- `knowledge/files/src/test/regress/pg_regress.c.md` — implementation
  of the driver.
- `knowledge/files/src/test/regress/pg_regress_main.c.md` — psql
  flavor's `main()`.
- `knowledge/files/src/test/isolation/isolation_main.c.md` —
  isolation flavor's `main()`.
