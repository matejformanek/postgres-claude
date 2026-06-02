# Eval 1 — with_skill (iter-2)

You're in the two-clone split: `source/` is read-only, `dev/` is mutable.
The edit landed under `dev/src/backend/access/heap/heapam.c` (via the
`dev/` symlink). Build artifacts go inside `dev/build-debug` and
`dev/install-debug`. The skill's new "edit -> rebuild -> retest cycle"
section spells this out:

## Fastest cycle

From the project root `/Users/matej/Work/postgres/postgres-claude/`:

```bash
# 1. Incremental rebuild + install. ninja recompiles only what changed.
ninja -C dev/build-debug install

# 2. Restart the postmaster. CRITICAL: the running postmaster is still
#    mapped to the previous `postgres` image; every backend it forks for
#    a new psql connection inherits the OLD image. ninja install only
#    updates the on-disk binary — without a restart your edits are invisible.
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"
pg_ctl -D "$PGDATA" restart

# 3. Smoke-test via the macOS Unix socket dir (/tmp)
psql -h /tmp -d postgres -c 'SELECT 1;'
```

Use the slash-command wrappers (listed at the top of the skill) for the
batteries-included path:

- `/setup-pg` → `.claude/commands/setup-pg.md` (configure + build + install,
  idempotent).
- `/pg-restart` → `.claude/commands/pg-restart.md` (stop -m fast, then
  start — exactly what's needed after `ninja install`).
- `/pg-psql` → `.claude/commands/pg-psql.md` (`psql -h /tmp -d postgres`).

## Regression check

The `regress` suite needs the `setup` suite to run first, otherwise
`tmp_install/` and `initdb-template/` are missing and you'll hit
`copying of initdb template failed`:

```bash
meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
```

Or via the slash command, which always prepends `--suite setup`:

```
/pg-test --suite regress
```

(See `.claude/commands/pg-test.md`.) Wall time ~33s on Apple Silicon plus
~7s for setup.

On failure, diffs land under
`dev/build-debug/testrun/regress/regress/results/` vs `expected/`;
full log at `dev/build-debug/meson-logs/testlog.txt`.

## Why these choices

- Build inside `dev/`, never `source/` — `source/` is the read-only
  reference used for stable file:line citations.
- `--buildtype=debug` + `-Dcassert=true` baked in at `meson setup` time,
  so every rebuild keeps `Assert()` macros live.
- The postmaster restart is non-negotiable after `ninja install`: a fresh
  `psql` forks a backend from the still-running postmaster, which still
  holds the old `postgres` image until restart.
