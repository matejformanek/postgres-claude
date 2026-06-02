# Eval 2 — with_skill (iter-2)

This is the canonical "missing setup suite" pitfall called out in
`.claude/skills/build-and-run/SKILL.md` ("Gotcha: `meson test --suite regress`
alone fails with `copying of initdb template failed` because the `setup`
suite … hasn't run").

## Why it dies

PG's meson harness splits "build the throwaway install tree" into its own
test suite named `setup`. That suite creates:

- `dev/build-debug/tmp_install/` — a private install prefix
- `dev/build-debug/tmp_install/initdb-template/` — pre-initdb'd data dir
  reused by every test cluster (the `initdb_cache` step)
- `install_test_files` — copies test inputs into the build tree

If you select `--suite regress` (or `isolation`, or anything else) without
also asking for `--suite setup`, meson runs *only* the suite you named.
The regress harness then tries to copy an initdb template that was never
built, and you get `copying of initdb template failed`.

## Fix

Always include `--suite setup` alongside the suite you actually want:

```bash
meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
```

Or use the slash command, which always prepends `--suite setup` for you —
see `.claude/commands/pg-test.md` (also indexed at the top of the skill):

```
/pg-test --suite regress
```

Filtering to a single test:

```bash
meson test -C dev/build-debug --suite setup --suite regress --test create_table
```

## The general rule

This rule generalizes: **any time you filter to a specific suite, prepend
`--suite setup`**. Same applies to `isolation`, `recovery`, `subscription`,
`pg_upgrade`. The slash-command wrapper exists precisely so you don't have
to remember.

## After it runs

- Full log: `dev/build-debug/meson-logs/testlog.txt`
- Per-test output / diff on failure:
  `dev/build-debug/testrun/regress/regress/results/regression.diffs`

## What NOT to do

Don't wipe `dev/build-debug` or `meson setup --reconfigure` — the build
is fine; the only thing missing is the setup-suite artifacts, which the
single corrected command above produces in ~7 seconds.
