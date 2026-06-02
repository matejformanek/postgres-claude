# Eval 1 — with_skill

You're working in this repo's two-clone split: `source/` is read-only, `dev/`
is mutable. The edited file lives under `dev/src/backend/access/heap/heapam.c`
(via the `dev/` symlink). All build artifacts go inside `dev/build-debug` and
`dev/install-debug`. See `.claude/skills/build-and-run/SKILL.md`.

## Fastest cycle

From the project root `/Users/matej/Work/postgres/postgres-claude/`:

```bash
# 1. Incremental rebuild + install. ninja figures out the minimal recompile.
ninja -C dev/build-debug install

# 2. Bounce the postmaster so it picks up the new `postgres` binary
#    (the running one is still mapped to the old image).
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"
pg_ctl -D "$PGDATA" stop -m fast
pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start

# 3. Smoke-test with psql against the macOS Unix socket dir (/tmp)
psql -h /tmp -d postgres -c 'SELECT 1;'
```

Or use the slash commands that wrap this exact flow:

- `/setup-pg` → `.claude/commands/setup-pg.md` (configure + build + install,
  idempotent — skips meson setup if `build.ninja` already exists).
- `/pg-restart` → `.claude/commands/pg-restart.md` (stop -m fast, then start;
  needed after any reinstall because the running backend is still on the old
  binary).
- `/pg-psql` → `.claude/commands/pg-psql.md` (`psql -h /tmp -d postgres`).

## Regression check

Run the `regress` suite — but the meson `setup` suite must run alongside
otherwise `tmp_install/` and `initdb-template` aren't built and you'll get
`copying of initdb template failed`:

```bash
meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
```

Or via slash command: `/pg-test --suite regress` (the wrapper at
`.claude/commands/pg-test.md` always prepends `--suite setup`). Wall time is
~33s on Apple Silicon plus ~7s for setup.

On failure, diffs land in
`dev/build-debug/testrun/regress/regress/results/` vs `expected/`; full log
in `dev/build-debug/meson-logs/testlog.txt`.

## Why these choices

- Build inside `dev/`, never `source/` — `source/` is the read-only reference
  used for stable file:line citations.
- `--buildtype=debug` + `-Dcassert=true` were baked in at `meson setup` time;
  every rebuild keeps `Assert()` macros live.
- After `ninja install`, the *running* postmaster still holds the previous
  `postgres` image — you must restart for code changes to take effect (a new
  `psql` connection forks a backend from the postmaster, which is still old).
