---
name: build-and-run
description: How to configure, build, and run PostgreSQL from `dev/` (the mutable test clone) for development. Covers the meson primary toolchain (PG ≥ 16 default), the autoconf fallback, debug build flags, `initdb` + start/stop, single-user mode, and the per-connection fork-model gotcha. Use whenever the task involves actually building, running, or debugging a backend.
---

# build-and-run

## Repo split — important

There are TWO upstream clones in the parent dir, both symlinked into this meta repo:

- `source/` → `../postgresql/` — **read-only reference**. Kept exactly in sync
  with upstream `master`. Used for code citations in `knowledge/...` docs.
  Never build or run from here.
- `dev/` → `../postgresql-dev/` — **mutable test field**. All build artifacts
  (`build-debug/`, `install-debug/`, `data-debug/`) live inside here. Safe to
  delete and re-clone (`rm -rf postgresql-dev && git clone --no-hardlinks postgresql postgresql-dev`).
  This is also where any local patches / experimental branches live.

When citing source code in docs use `source/...` paths (stable). When running
commands that build, install, initdb, or modify the tree, use `dev/...`.

## Toolchain choice — meson is the default

Since PG 16, meson is the primary build system. autoconf still works and the
buildfarm still exercises it, but new instructions assume meson unless told
otherwise.

## One-time setup (debug build)

From `postgres-claude/`:

```bash
# out-of-tree build dir, kept beside dev/'s source
meson setup dev/build-debug dev \
  --buildtype=debug \
  -Dcassert=true \
  -Ddebug=true \
  -Dprefix=$PWD/dev/install-debug

ninja -C dev/build-debug
ninja -C dev/build-debug install
```

Notes:

- `cassert=true` turns on the `Assert()` macros — invaluable when reading internals.
- `--buildtype=debug` (not `debugoptimized`) keeps symbols readable in gdb/lldb.
- Build dir is `dev/build-debug` so it sits inside the mutable clone and is
  ignored upstream by `build*/`. The dev clone's `.git/info/exclude` also
  ignores `build-debug/`, `install-debug/`, and `data-debug/` so PG-relative
  status is always clean.

## Initialize a cluster and start it

```bash
export PGDATA=$PWD/dev/data-debug
export PATH=$PWD/dev/install-debug/bin:$PATH

initdb -D "$PGDATA" --locale=C --encoding=UTF8
pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start
psql -h /tmp -d postgres
# ...
pg_ctl -D "$PGDATA" stop -m fast
```

## The per-connection fork model — critical gotcha

PostgreSQL uses a **process-per-connection** model. The postmaster forks a new
backend process for every incoming `psql` connection. Implications when
debugging:

- Attaching gdb to the postmaster does *not* let you step through query
  execution — query execution happens in the forked child.
- The pattern is: connect with `psql`, get the backend PID with
  `SELECT pg_backend_pid();`, then `gdb -p <pid>` in another terminal.
- Or use `--single` (single-user mode, no postmaster, no fork) for stepping
  through startup-time code paths.

## Single-user mode

```bash
postgres --single -D "$PGDATA" postgres
```

Runs the backend in the foreground bound to your terminal. No SQL frontend,
no fork. Useful for debugging code that runs early in backend startup or for
running short SQL non-interactively under a debugger.

## Useful debug knobs

- `log_min_messages = debug5` in `postgresql.conf` for maximum verbosity.
- `log_statement = 'all'` to see every statement.
- `client_min_messages = debug1` per-session in `psql` for inline debug output.
- `debug_print_parse / debug_print_rewritten / debug_print_plan` for planner work.

## Running the regression tests

```bash
ninja -C dev/build-debug test         # full meson test target
# Or a single suite — MUST include --suite setup so tmp_install /
# initdb-template get built first:
meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
```

The `regress` suite is the headline one (~33s wall on Apple Silicon, plus
~7s for the `setup` suite that builds `tmp_install/` and the `initdb-template`).
`isolation` covers concurrency (serializable, predicate locks, etc.).
`recovery` covers crash & replication.

**Gotcha**: `meson test --suite regress` alone fails with `copying of initdb
template failed` because the `setup` suite (`tmp_install`,
`install_test_files`, `initdb_cache`) hasn't run. Always pass `--suite setup`
alongside any filtered suite selection.

## Common build pitfalls

- Stale build dir after pulling upstream — `ninja -C dev/build-debug clean`
  and re-`setup` if `meson.build` files changed significantly.
- Linker errors after switching branches with extension SQL changes —
  re-`install` to refresh `dev/install-debug/share/`.
- `initdb` failing with locale error on macOS — use `--locale=C` (above)
  rather than the system default.

## Where the build artifacts you'll touch live

- Binaries: `dev/install-debug/bin/{postgres,psql,pg_ctl,initdb,…}`
- Shared libraries / extensions: `dev/install-debug/lib/`
- Default extension SQL: `dev/install-debug/share/extension/`
- Per-cluster data: `dev/data-debug/` (created by `initdb`)
- Server log: `dev/data-debug/server.log`
