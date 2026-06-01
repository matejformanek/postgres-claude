---
name: testing
description: Pick the right PostgreSQL test flavor for a core/contrib patch — pg_regress .sql/.out pairs, isolationtester specs and permutations for concurrency/deadlock races, TAP (PostgreSQL::Test::Cluster) for multi-node and pg_basebackup/replication scenarios, and src/test/modules for in-tree C test modules. Covers where files live and how to run a single test fast. Use whenever adding or reviewing tests on a PG patch, or asked "regress vs isolation vs TAP" for a feature or bug. Skip pytest/Jest/Go testing/RSpec and pgbench benchmarking questions.
---

# Testing PostgreSQL — decision tree

Companion to `knowledge/conventions/testing.md`. That file is the long-form
reference; this is the action card.

## Step 1: Pick the flavor

Answer these in order. **First "yes" wins.**

1. **Does the behavior need multiple sessions / concurrent transactions /
   heavyweight-lock contention?**
   → **isolation spec** in `source/src/test/isolation/specs/<name>.spec`.
   Caveat: `isolationtester` only sees heavyweight locks via `pg_locks`. LWLock /
   buffer-pin contention → use injection points or a C test module instead.

2. **Does it need initdb, a restart, multiple clusters, replication, a backup,
   a signal, or testing a CLI tool (`pg_dump`, `pg_basebackup`, `pg_rewind`)?**
   → **TAP test** in the appropriate `t/` dir:
   - Recovery / replication → `source/src/test/recovery/t/NNN_name.pl`
   - Logical replication → `source/src/test/subscription/t/NNN_name.pl`
   - Auth → `source/src/test/authentication/t/NNN_name.pl`
   - SSL → `source/src/test/ssl/t/NNN_name.pl`
   - A specific CLI tool → `source/src/bin/<tool>/t/NNN_name.pl`
   - Contrib extension → `source/contrib/<ext>/t/NNN_name.pl`
   - Brand new area without an obvious home → ask before creating a directory.

3. **Are you testing a C-level hook, internal API, or something only reachable
   from C?**
   → Add (or extend) a test module under `source/src/test/modules/<name>/`,
   then drive it from a `.sql` or TAP test in the same module dir.

4. **Else** (pure SQL: planner, builtin function, DDL, error message, catalog
   behavior): **regress test**. `source/src/test/regress/sql/<name>.sql` +
   `expected/<name>.out`, wired into `parallel_schedule`.

## Step 2: Wire it in (don't skip — easiest mistake)

| Flavor | File you must edit |
|---|---|
| regress | `source/src/test/regress/parallel_schedule` (add to a `test:` line, max 20 per group) |
| isolation | `source/src/test/isolation/isolation_schedule` (`test: <name>`) |
| TAP | `meson.build` in the same dir as `t/` (e.g. `source/src/test/recovery/meson.build`) AND the `Makefile` if one exists |
| modules | `source/src/test/modules/meson.build` if adding a new module dir |

## Step 3: Generate expected output

For regress and isolation: write the `.sql` / `.spec`, run the test, copy the
produced output to `expected/`:

```bash
# regress
meson test -C build regress/regress    # will FAIL the first time
cp source/src/test/regress/results/<name>.out source/src/test/regress/expected/<name>.out
# now re-run and check it passes
meson test -C build regress/regress
```

**Always read the generated `.out` before committing.** Anything OID-y,
timestamp-y, or row-order-y is a future buildfarm failure. Cast it, ORDER BY it,
or `SET` it away.

## Step 4: Run only your test (fast loop)

```bash
# Single TAP test
meson test -C build --suite recovery 001_stream_rep -v

# Single isolation spec
cd build/src/test/isolation && \
  ./pg_isolation_regress --temp-instance=/tmp/iso \
    --top-builddir=../../../.. <spec_name>

# Single regress test
cd build/src/test/regress && \
  ./pg_regress --temp-instance=/tmp/pgr \
    --top-builddir=../../../.. <test_name>

# Whole suite by name
meson test -C build --suite regress
meson test -C build --suite isolation
meson test -C build --suite recovery
```

`make` equivalents (from `source/src/test/<area>/`):
- `make check` — fresh temp instance, what CI does. Use before submitting.
- `make installcheck` — against your running cluster. Faster, less safe.
- `make check PROVE_TESTS=t/NNN_name.pl` — just one TAP test.

## Step 5: When it fails

- **regress**: open `build/src/test/regress/regression.diffs` first. If the diff
  is what you want, copy `results/<name>.out` over `expected/<name>.out`.
- **isolation**: `build/src/test/isolation/output_iso/regression.diffs`.
  Hanging = invalid permutation (a step blocks with nothing to unblock it).
- **TAP**: `build/testrun/<suite>/<test>/log/regress_log_*` is the Perl-side log.
  Read it before the postmaster logs. Set `PG_TEST_NOCLEAN=1` to keep
  `tmp_check/` even on success.

## Cheat sheet — decision in one line

> *"Multiple sessions? → isolation. Initdb-or-restart? → TAP. C hook? → module.
> Otherwise → regress."*

## Common rejections in review

- "Use a regress test, not TAP" — for anything expressible in SQL.
- "Output isn't stable" — OIDs, timestamps, plan costs, unsorted results.
- "Add it to the schedule" — file exists but isn't wired into `parallel_schedule`
  / `isolation_schedule` / `meson.build`.
- "Don't introduce `_1.out` variants" — prefer to stabilize the test
  (markers in isolation; `SET` / casts in regress).
- "Renumbered existing TAP tests" — breaks backports. Always append `NNN`.
- "Uses non-core Perl module" — only `IPC::Run` is allowed; everything else
  must be in Perl 5.14 core.

See `knowledge/conventions/testing.md` for full citations and the long form.
