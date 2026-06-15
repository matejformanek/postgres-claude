---
path: src/interfaces/ecpg/test/pg_regress_ecpg.c
anchor_sha: e18b0cb7344
loc: 266
depth: read
---

# src/interfaces/ecpg/test/pg_regress_ecpg.c

## Purpose

The **ecpg-flavor `pg_regress` driver**. It is the analog of
`src/test/regress/pg_regress_main.c` (for the SQL backend regress) and
`src/test/isolation/isolation_main.c` (for the isolation tester): a thin
`main()` that supplies three ecpg-specific callbacks to the shared
`regression_main()` framework declared in `pg_regress.h`. Each test name
in the schedule corresponds to a pre-built standalone executable
(generated from a `.pgc` source by the ecpg preprocessor then compiled
against ecpglib); the driver runs that exe, captures three streams
(`.stdout`, `.stderr`, the preprocessed `.c`), filters them, and lets the
framework diff each against `expected/<name>.{stdout,stderr,c}`.
`[verified-by-code]` (`pg_regress_ecpg.c:147-236, 259-266`)

Originally a shell script; rewritten in C by Magnus Hagander for
portability. `[from-comment]` (`pg_regress_ecpg.c:5-7`)

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int main(int argc, char *argv[])` | `pg_regress_ecpg.c:259-266` | one-line forwarder to `regression_main()` with the three ecpg callbacks |

All other functions are `static` — they are the callbacks passed to
`regression_main`.

## Internal landmarks

### `ecpg_filter_source(sourcefile, outfile)` — `pg_regress_ecpg.c:33-80`

Copies the `.c` file ecpg produced from the `.pgc` input, but **strips
directory paths out of `#line` directives**. ecpg emits
`#line N "./../bla/foo.h"`; the path part varies with compiler / VPATH /
platform, so the filter rewrites it to just `#line N "foo.h"`. The
mechanism: spot lines that begin with `#line `, find the opening `"`,
then advance past any `.` / `/` characters and `memmove` the rest of the
string down. `pg_get_line_buf()` reads variable-length lines into a
`StringInfo`, so arbitrary long source lines work.

### `ecpg_filter_stderr(resultfile, tmpfile)` — `pg_regress_ecpg.c:92-140`

Sanitizes connection-failure messages **in place** in a `.stderr` result
file. libpq emits `connection to server <details> failed: <reason>` where
`<details>` includes pathnames and ports that vary per run. The filter
collapses `connection to server …failed:` to a fixed-length prefix
(exactly 21 bytes — `strlen("connection to server ")`) followed by the
literal `failed: <reason>`. Then it `rename()`s the temp file over the
original. `[from-comment]` (`pg_regress_ecpg.c:82-91`)

The comment acknowledges this and `ecpg_filter_source` could share a
generic pattern matcher but explicitly **declines** to introduce a regex
dependency for the small benefit. `[from-comment]`
(`pg_regress_ecpg.c:87-91`)

### `ecpg_start_test(testname, resultfiles, expectfiles, tags)` — `pg_regress_ecpg.c:147-236`

The heart of the driver. For each schedule entry it:

1. **Computes paths.** `inprg = inputdir/testname` (the pre-built exe);
   `insource = inputdir/testname.c` (the ecpg-emitted C source).
   `pg_regress_ecpg.c:166-167`.
2. **Builds a "testname-dash" string** by copying `testname` and replacing
   `/` with `-`. Schedule entries are written `subdir/foo` but result
   files must be flat filenames: `subdir-foo.stdout` etc.
   `pg_regress_ecpg.c:169-176`.
3. **Builds six paths** — three `expectfile_*` under `expecteddir/expected/`
   (`.stdout`, `.stderr`, `.c`) and three `outfile_*` under
   `outputdir/results/` — and registers all three (result, expect, tag)
   triples with the framework so the post-run diff stage compares each.
   `pg_regress_ecpg.c:178-208`. The tags `"stdout"`, `"stderr"`, `"source"`
   appear in failure reports.
4. **Filters the source up-front** by calling `ecpg_filter_source(insource,
   outfile_source)` — this writes the path-stripped C source into
   `results/` so the diff against `expected/<n>.c` is meaningful.
   `pg_regress_ecpg.c:210`.
5. **Spawns the test exe** with stdout/stderr redirected to the two result
   files: `"prg" >"out.stdout" 2>"out.stderr"`. `pg_regress_ecpg.c:212-216`,
   `222`.
6. **Sets `PGAPPNAME`** to `ecpg/<testname-dash>` around the spawn so the
   server's log shows which test issued each query.
   `pg_regress_ecpg.c:218-220, 231`.

Returns the spawned PID; the framework reaps it and triggers the diff.

### `ecpg_postprocess_result(filename)` — `pg_regress_ecpg.c:238-251`

Called by the framework once per result file before diffing. Only the
`.stderr` files need touching (`if .stderr` → call
`ecpg_filter_stderr`); `.stdout` and `.c` pass through. The `.c` files
were already filtered up-front at spawn time inside `ecpg_start_test`.

### `ecpg_init` — `pg_regress_ecpg.c:253-257`

Empty stub. Reserved hook for one-time setup; ecpg currently needs none.

## Invariants & gotchas

- **Two-stage filtering.** `.c` is filtered at spawn time (before the
  child runs, into `outfile_source`); `.stderr` is filtered after the
  child exits via `ecpg_postprocess_result`. Don't refactor this into a
  single post-pass — the `.c` file isn't generated by the child at all,
  it's the static product of the build.
- **`linebuf.len` not updated** after the `memmove` shrinks lines
  (`pg_regress_ecpg.c:71, 125` `[from-comment]`). Fine because the buffer
  is immediately re-used with `pg_get_line_buf` (which resets it) on the
  next iteration; the contents are written with `fputs` which honors the
  NUL terminator, not `.len`.
- **Three diff streams per test** — `.stdout`, `.stderr`, `.c` — is
  ecpg-specific. Regular `pg_regress` diffs only `.out`. This is why ecpg
  cannot just reuse `pg_regress_main.c`: it has to ship a `.c` against an
  `expected/<n>.c` to catch preprocessor regressions, not just runtime
  ones.
- **Exit code 2** on any I/O failure inside the filters
  (`pg_regress_ecpg.c:44, 50, 102, 108, 138, 228`). The framework treats
  this as a hard test-driver failure, distinct from test-content
  failures.
- **`spawn_process` and `INVALID_PID`** come from `pg_regress.h` and
  abstract over fork/exec vs `_spawnv` on Windows.
- **No locking, no parallelism here.** `regression_main()` may run
  multiple tests concurrently; this callback is invoked once per test in
  whatever worker the framework decides. The filters operate on per-test
  files only, so there's no shared state to protect.

## Cross-refs

- `knowledge/files/src/test/regress/pg_regress.c.md` — the shared
  framework providing `regression_main`, `spawn_process`,
  `_stringlist`, `inputdir`/`outputdir`/`expecteddir`, and the diff stage.
- `knowledge/files/src/test/regress/pg_regress_main.c.md` — sibling
  driver for the SQL backend regress (the analog this file mirrors).
- `knowledge/files/src/interfaces/ecpg/preproc/` — the preprocessor that
  produced the `.c` files this driver diffs.
- `knowledge/files/src/interfaces/ecpg/test/regression.h.md` — the
  per-test ecpg include defining the throwaway DB/role names.
- `knowledge/files/src/interfaces/ecpg/test/printf_hack.h.md` — the
  per-test stdout-stability helper.
