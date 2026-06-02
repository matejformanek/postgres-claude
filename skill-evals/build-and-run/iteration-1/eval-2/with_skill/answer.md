# Eval 2 — with_skill

That failure is the canonical "missing setup suite" pitfall called out in
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

If you select `--suite isolation` (or `regress`, or anything else) without
also asking for `--suite setup`, meson runs *only* the suite you named.
The isolation harness then tries to copy the initdb template that was never
built, and you get `copying of initdb template failed`.

## Fix

Always include `--suite setup` alongside the suite you actually want:

```bash
meson test -C dev/build-debug --suite setup --suite isolation --num-processes 4
```

Or use the slash command, which always prepends `--suite setup` for you —
see `.claude/commands/pg-test.md`:

```
/pg-test --suite isolation
```

Filtering to a single isolation spec:

```bash
meson test -C dev/build-debug --suite setup --suite isolation --test deadlock-soft
```

## After it runs

- Full log: `dev/build-debug/meson-logs/testlog.txt`
- Per-spec output / diff on failure:
  `dev/build-debug/testrun/isolation/isolation/output_iso/regression.diffs`

## Related

`isolation` covers concurrency (predicate locks, SSI, deadlock detection).
Same `--suite setup` rule applies to `recovery`, `subscription`, `pg_upgrade`,
etc. — any time you filter, prepend setup.
