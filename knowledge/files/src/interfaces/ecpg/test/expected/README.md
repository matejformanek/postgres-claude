---
path: src/interfaces/ecpg/test/expected/
anchor_sha: e18b0cb7344
loc: aggregate
depth: read
---

# src/interfaces/ecpg/test/expected/ — golden ecpg preprocessor outputs

This directory is the authoritative documentation for everything under
`src/interfaces/ecpg/test/expected/`. The 69 `.c` files here are NOT
hand-written sources — they are **golden outputs of the ecpg
preprocessor**, committed alongside their `.pgc` test inputs and diffed
at regression time. Per-file docs under this dir are intentionally thin
stubs; this README is the real content.

## Purpose

The ecpg preprocessor (`src/interfaces/ecpg/preproc/ecpg`) translates
Embedded SQL in C (`.pgc`) into pure C (`.c`). For each test input
`.../<category>/<name>.pgc` there is a corresponding golden output
`expected/<category>-<name>.c` that nails down the preprocessor's
exact textual behavior. The `.stdout` / `.stderr` siblings nail down
the **runtime** behavior of the compiled-and-linked binary.

Together they form a two-layer regression net:

- **Preprocessor regression** — `expected/<...>.c` vs freshly-produced
  `.c`. Catches changes to how ecpg lowers ESQL constructs into libecpg
  calls.
- **Runtime regression** — `expected/<...>.stdout` / `.stderr` vs the
  compiled binary's actual output against a live server. Catches
  changes to libecpg, pgtypeslib, or backend behavior visible through
  ecpg.

A diff failure on `expected/<...>.c` is almost always a preprocessor
change — intended or not. Either accept and update the golden, or
revert the preprocessor edit.

## Naming convention

Outputs are flattened: `expected/<category>-<name>.c` corresponds to
input `../<category>/<name>.pgc`. The dash replaces the directory
separator so all expected files live in one flat dir.

Examples:

| Expected file                                | Source input                          |
| -------------------------------------------- | ------------------------------------- |
| `expected/sql-describe.c`                    | `../sql/describe.pgc`                 |
| `expected/preproc-cursor.c`                  | `../preproc/cursor.pgc`               |
| `expected/compat_informix-test_informix.c`   | `../compat_informix/test_informix.pgc`|
| `expected/thread-thread.c`                   | `../thread/thread.pgc`                |

There is also a `.stdout` (and sometimes `.stderr`) per test, with the
same naming, holding the expected program output.

## How regenerated

The build rule lives in `src/interfaces/ecpg/test/Makefile.regress:27-28`:

```make
%.c: %.pgc $(ECPG_TEST_DEPENDENCIES)
    $(ECPG) -o $@ $<
```

where `$(ECPG) = ../../preproc/ecpg --regression -I... -I$(srcdir)`
(Makefile.regress:13). The `--regression` flag makes ecpg emit
deterministic output (no `#line` paths leaking the build host's
absolute directory, etc.) so the goldens are diffable across machines.

At test time, `pg_regress_ecpg`
(`src/interfaces/ecpg/test/pg_regress_ecpg.c`) drives the per-test
flow: compile the `.pgc` via ecpg + cc, run the binary against a
temporary cluster, capture stdout/stderr, then diff against
`expected/<...>.c`, `.stdout`, and `.stderr`. The Meson equivalent is
in `src/interfaces/ecpg/test/meson.build` and the per-category
`*/meson.build` files; they hand the same list of tests to
`pg_regress_ecpg` via the `ecpg_schedule` file.

**Updating a golden.** When a preprocessor change intentionally
shifts output, regenerate by re-running the build (the `.c` is rebuilt
from `.pgc`) and committing the new `expected/<...>.c`. Reviewers should
see a focused diff showing only the lowering change.

## Reading them by hand

These files are **machine output**. Don't read them top-to-bottom
looking for hand-written intent — there isn't any. The useful reading
patterns are:

1. **Side-by-side with the `.pgc` input.** Open
   `source/src/interfaces/ecpg/test/<category>/<name>.pgc` next to
   `source/src/interfaces/ecpg/test/expected/<category>-<name>.c` and
   read the ESQL construct → libecpg-call mapping.
2. **`git log` on the golden.** Each commit that touched the file
   typically shows what preprocessor change forced the regeneration.
3. **Diff between two branches.** When working on an ecpg preprocessor
   patch, `git diff master -- src/interfaces/ecpg/test/expected/` is
   the fastest way to see the full output surface impact.

The `#line` directives, `ECPGdo(...)` calls, `sqlca` declarations, and
struct initializers in these files are all preprocessor templates —
their **shape** is what's being pinned, not their content.

## Categories

The 69 expected `.c` files come from seven test category
subdirectories under `src/interfaces/ecpg/test/`:

- **connect/** (6 files, `connect-test1.c` … `connect-test6.c`) —
  EXEC SQL CONNECT / SET CONNECTION / DISCONNECT semantics: connection
  names, default connections, error paths. Tests live against
  `regress1` / `regress2` databases set up by `pg_regress_ecpg`.
- **preproc/** (14 files) — pure preprocessor features with no
  required server interaction beyond a smoke connect: comments,
  `EXEC SQL DEFINE`, type definitions, struct/array host variables,
  cursors, WHENEVER actions, `outofscope` host-variable visibility,
  pointer-to-struct, autoprep mode.
- **pgtypeslib/** (5 files) — exercises the pgtypeslib C support
  library directly (date, timestamp, numeric, decimal, NaN handling).
  These tests mostly run pure-C code with minimal SQL.
- **sql/** (28 files) — the bulk: feature coverage of the SQL surface
  ecpg supports — DESCRIBE, FETCH, EXECUTE, PREPARE, dynamic SQL,
  SQLDA, descriptors, two-phase commit, COPY, arrays, bytea, indicators,
  SQL/JSON, SQL/PGQ, etc.
- **thread/** (5 files) — multi-threaded ecpg programs: per-thread
  connections, descriptors, prepared statements, the allocator. Only
  built when threading is available.
- **compat_informix/** (10 files) — `-C INFORMIX` mode: Informix-style
  decimal, date formats, `rfmtdate`/`rfmtlong`, `rnull`, `sqlda`,
  `intoasc`, charfuncs.
- **compat_oracle/** (1 file, `compat_oracle-char_array.c`) —
  `-C ORACLE` mode: Oracle-style fixed-length char-array handling.

## Why we don't write per-file docs for these

Each `.c` file under this directory is fully derived from its `.pgc`
sibling by a deterministic tool. There is no hand-authored content to
extract — no design decision lives in the output that doesn't live in
either the input or in `src/interfaces/ecpg/preproc/`. Writing 69
near-identical "this is machine output for `<x>.pgc`" docs would only
add noise to the corpus.

The stubs that DO exist (one per file) are coverage markers so the
file-by-file census tool counts the dir as documented; they each
point back here.

For the actual semantics of any lowering, read:

- The matching `.pgc` input — for the ESQL construct under test.
- `knowledge/files/src/interfaces/ecpg/preproc/*.md` — for the
  preprocessor logic that produced the lowering.

## When to consult them

- **Regression triage.** A `make check` failure under `ecpg` with a
  diff against `expected/<...>.c` means a preprocessor edit changed
  the output. Look at the diff, decide accept-or-revert.
- **Reviewing an ecpg preprocessor patch.** Diff of `expected/` is the
  patch's "behavior surface" — small surface = focused change; broad
  surface = potentially-disruptive change worth scrutiny.
- **Onboarding to ecpg.** Reading a few `.pgc` ↔ `.c` pairs is a
  faster way to internalize the preprocessor's lowering model than
  reading the grammar.

## Cross-refs

- `knowledge/files/src/interfaces/ecpg/preproc/` — the preprocessor
  that produces these outputs (grammar, lexer, output emission).
- `knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md` —
  the regression driver that compares produced output against these
  goldens.
- `source/src/interfaces/ecpg/test/Makefile.regress` — the
  `%.c: %.pgc` rule that regenerates them.
- `source/src/interfaces/ecpg/test/ecpg_schedule` — the test schedule
  consumed by `pg_regress_ecpg`.
- `source/src/interfaces/ecpg/test/meson.build` and per-category
  `*/meson.build` — Meson plumbing for the same flow.
