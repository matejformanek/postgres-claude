---
description: Run PostgreSQL test suites via meson. Defaults to the regress suite. Supports --suite NAME and --test PATTERN.
---

# pg-test

Run PG's test suites against `dev/build-debug/`.

## What to run

Parse flags from `$ARGUMENTS`. Default: full meson test (regress + many others).

```bash
SUITE=""
TESTPAT=""
# crude flag parsing — user invokes /pg-test --suite isolation --test deadlock
# pass through ARGUMENTS; expected forms:
#   /pg-test
#   /pg-test --suite regress
#   /pg-test --suite isolation --test deadlock-soft
#   /pg-test --num-processes 8

# Sensible default: regress + the setup suite it depends on, 4 processes
if [ -z "$ARGUMENTS" ]; then
  meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
else
  # Pass user args straight through to meson test, but always include --suite setup
  # so tmp_install / install_test_files / initdb_cache run first.
  meson test -C dev/build-debug --suite setup $ARGUMENTS
fi
```

If the user said `--test FOO` without `--suite`, default to `--suite regress`.

**CRITICAL**: PG's meson test layout has a separate `setup` suite that creates
`build-debug/tmp_install/` and `initdb-template/`. If you select a single suite
(e.g. `--suite regress`) without also selecting `--suite setup`, the harness
will fail with `copying of initdb template failed` / `tmp_install/initdb-template:
No such file or directory`. Always include `--suite setup` when filtering.

## Common suites

- `regress` — the headline SQL regression tests. Run this first. ~34s on M-series.
- `isolation` — concurrency tests (predicate locks, SSI, deadlock detection).
- `recovery` — crash recovery, replication, WAL replay. Requires perl IPC::Run.
- `subscription` — logical replication. Slow.
- `pg_upgrade` — upgrade tests. Slow.
- `ssl`, `ldap`, `kerberos` — only if the corresponding `-D*=enabled` was set
  at configure time (this dev build does NOT include kerberos/gss).

## After running

- Read `dev/build-debug/meson-logs/testlog.txt` for full output.
- Failures dump diffs into `dev/build-debug/testrun/<suite>/regress/results/`
  vs `expected/`. Show the user the diff path on any failure.

## Troubleshooting

- **`Could not find perl module IPC::Run`** for recovery/subscription suites:
  `cpan IPC::Run` or `brew install perl` + `cpanm IPC::Run`.
- **Tap tests fail with locale errors on macOS**: tests use `LC_ALL=C` internally;
  if you see locale issues, ensure your shell isn't forcing a UTF-8 collation
  that the cluster doesn't have.
- **Stale results**: `ninja -C dev/build-debug clean-testfiles` or just remove
  `dev/build-debug/testrun/`.
