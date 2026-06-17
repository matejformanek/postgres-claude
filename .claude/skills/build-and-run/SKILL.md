---
name: build-and-run
description: Build, install, initdb, and start PostgreSQL from source in the `dev/` clone for backend hacking — covers meson setup (PG ≥ 16 default) with cassert + debug flags, the autoconf ./configure fallback, ninja install, initdb + pg_ctl start / stop, PGDATA / PATH wiring, single-user mode for postmaster startup debugging, attaching gdb / lldb under the per-connection fork model, and -O0 -g3 debug builds. Use whenever a task involves compiling PG from source in dev/, running ninja install on the dev clone, initdb-ing a fresh data directory, starting or stopping the dev cluster via pg_ctl, picking between the debug profile (5432) and ASan profile (5433), or attaching a debugger to a forked backend. Skip for brew / apt / yum / Docker / k8s installation of release PG, Aurora / Cloud SQL / Supabase / Neon-managed PG provisioning, generic CMake / make / Bazel build questions, Linux-kernel builds, Node.js / Python / Go application builds, and pgAdmin / DBeaver client installation.
when_to_load: Compile, install, initdb, start/stop, or wire PATH/PGDATA for the dev cluster; build the ASan profile; pick which build profile for a symptom.
companion_skills:
  - debugging
  - psql
  - testing
  - error-handling
---

# build-and-run

## Slash-command wrappers (use these first)

The recipes in this skill are also exposed as slash commands under
`.claude/commands/`. Prefer them — they encode the right flags and
guardrails:

- `/setup-pg` — first-time meson setup + build + install (idempotent;
  `--force` to reconfigure).
- `/pg-start`, `/pg-stop`, `/pg-restart` — lifecycle.
- `/pg-psql` — `psql -h /tmp -d postgres` against the dev cluster.
- `/pg-test [--suite NAME] [--test PAT]` — meson test, always prepends
  `--suite setup` so the initdb-template trap can't bite.
- `/pg-attach` — get a backend PID and print the `lldb -p` line.
- `/pg-tail-log` — follow `dev/data-debug/server.log`.
- `/pg-fresh --yes` — wipe `data-debug/`, re-initdb (preserves the build).
- `/pg-reclone-dev` — nuclear: re-clone the whole dev tree from the
  read-only reference.
- `/setup-pg-asan` / `/pg-start-asan` — sibling profile built with
  AddressSanitizer + UndefinedBehaviorSanitizer (see "Sanitizer builds"
  below); use this when chasing memory bugs or undefined behavior.

The rest of this file is the underlying mechanics, for cases where you need
to deviate from the wrappers.

## Running these from a git worktree (gotcha)

Every `/pg-*` command above resolves paths via `$PWD/dev/...` and
`$PWD/source/...`. The `dev` and `source` symlinks live at the
**root of the postgres-claude repo**, and `git worktree add` (or this
project's `EnterWorktree` tool) does NOT propagate them into the new
worktree. Inside a worktree, the commands break with `No such file or
directory`.

Two ways to handle it:

1. **Run from main** (simplest). The pg-* commands are stateful — they
   touch the dev cluster, not the meta-repo source — so running them
   from main is harmless even when your edits live on a feature branch.
2. **Add symlinks per worktree** (when you genuinely need everything in
   one tree). One-liner from inside the worktree, using absolute paths so
   they don't drift:
   ```bash
   ln -s /Users/matej/Work/postgres/postgresql-dev dev
   ln -s /Users/matej/Work/postgres/postgresql     source
   ```
   These are local-only — they won't be tracked by git (the parent
   `.gitignore` excludes them) and ExitWorktree won't try to commit them.

## Sanitizer builds (`build-asan` profile)

The default `dev/build-debug/` enables Asserts + debug symbols but no
sanitizers. For memory-bug hunting (use-after-free, heap-buffer-overflow,
double-free, integer/signed overflow, alignment violations) build a
parallel `dev/build-asan/` profile with ASan + UBSan turned on:

```bash
meson setup dev/build-asan dev \
  --buildtype=debug \
  -Dcassert=true \
  -Ddebug=true \
  -Db_sanitize=address,undefined \
  -Db_lundef=false \
  -Dprefix=$PWD/dev/install-asan
ninja -C dev/build-asan
ninja -C dev/build-asan install
```

`-Db_lundef=false` is required on macOS / clang because ASan needs
runtime symbols resolved late; without it linking fails with "undefined
symbols for arch arm64: ___asan_init…".

To run the cluster against this build, point `PATH`/`PGDATA` at the asan
install + a separate data dir (so you can hop between debug + asan
clusters without `initdb` collisions):

```bash
export PATH="$PWD/dev/install-asan/bin:$PATH"
export PGDATA="$PWD/dev/data-asan"
[ ! -f "$PGDATA/PG_VERSION" ] && initdb -D "$PGDATA" --locale=C --encoding=UTF8
# ASan-specific runtime knobs:
export ASAN_OPTIONS="abort_on_error=1:detect_leaks=0:detect_stack_use_after_return=1:print_stacktrace=1"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"
pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start
```

`/setup-pg-asan` and `/pg-start-asan` wrap this exactly.

### macOS-specific caveats

- **LeakSanitizer is not available on Darwin.** `detect_leaks=0` above is
  required; setting `detect_leaks=1` errors out at runtime. For real leak
  detection you have three options:
  1. Build the asan profile on Linux (container or VM) — LSan works there.
  2. Use macOS-native `leaks <pid>` against the running backend (no
     rebuild needed). Set `MallocStackLogging=1` before `pg_ctl start`
     for proper backtraces; see the `debugging` skill.
  3. Use `pg_backend_memory_contexts` to watch a single context grow
     across a workload (also in the `debugging` skill).
- ASan still catches **use-after-free**, **heap-buffer-overflow**, and
  **double-free** on macOS, which is the common case for backend C bugs.
- The ASan slowdown is ~2-3x on PG workloads — fine for development,
  obviously not for benchmarking.

### Picking which profile to use

| Symptom / task                                   | Profile        |
| ------------------------------------------------ | -------------- |
| Normal feature work, stepping in lldb            | `build-debug`  |
| `Assert()` triggered, want to inspect            | `build-debug`  |
| SIGSEGV, suspected use-after-free, OOB write     | `build-asan`   |
| UB suspected (signed overflow, alignment, etc.)  | `build-asan`   |
| Leak chase                                       | `leaks` macOS or LSan on Linux |
| Performance work                                 | release build (separate prefix) |

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

### macOS — match the sibling `postgresql-dev/build-debug` config (F7)

On macOS, a fresh `meson setup build-debug` may need explicit ICU include
flags to match the existing sibling configuration that all the other
build trees use:

```bash
meson setup dev/build-debug dev \
  --buildtype=debug \
  -Dcassert=true \
  -Ddebug=true \
  -Dc_args='-I/opt/homebrew/opt/icu4c/include' \
  -Dprefix=$PWD/dev/install-debug
```

The reference configuration to mirror lives at
`/Users/matej/Work/postgres/postgresql-dev/build-debug` — when in doubt,
copy its `meson-info/intro-buildoptions.json` settings. Without the ICU
include path, configure trips when probing for `unicode/ucol.h` on
homebrew-arm64 setups.

Origin: sesvars calibration F7.

### First-run gotcha: the `setup` suite must run ONCE before `regress` (F7)

On a freshly-created `dev/build-debug/` tree (right after
`meson setup` + `ninja install`), the test harness has NOT yet built
`tmp_install/initdb-template/`. That artifact is produced by meson's
`setup` suite (targets `tmp_install`, `install_test_files`, and
critically `initdb_cache`). Until those run once, any `--suite regress`
invocation fails with:

```
copying of initdb template failed
... tmp_install/initdb-template: No such file or directory
... could not bind IPv4 address ...: Address already in use
```

Run the setup suite once before the first regress run:

```bash
meson test -C dev/build-debug --suite setup
# then, normally:
meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
```

The `/pg-test` wrapper prepends `--suite setup` for exactly this
reason, but a manual `meson test --suite regress` outside the wrapper
will silently fail without it.

Origin: sesvars calibration F7.

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

## The edit -> rebuild -> retest cycle

After editing any backend C file:

```bash
ninja -C dev/build-debug install       # incremental — ninja recompiles only what changed
pg_ctl -D "$PGDATA" restart            # CRITICAL — see below
psql -h /tmp -d postgres -c 'SELECT 1;'
```

**Why the restart is mandatory:** the running postmaster is still mapped to
the previous `postgres` image, and every backend it forks for new
connections inherits that image. `ninja install` only updates the on-disk
binary — without a restart, your edits are invisible. The same applies to
shared libraries / extensions under `dev/install-debug/lib/` and
`dev/install-debug/share/`.

Slash-command wrappers that automate this: `/setup-pg` (build+install),
`/pg-restart` (stop -m fast + start), `/pg-psql` (psql -h /tmp).
See `.claude/commands/`.

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

### Launching single-user mode under lldb

For startup paths (`InitPostgres`, recovery, GUC bootstrap, shmem init)
that run before any client connects, launch the backend *under* the
debugger so you're at instruction 0 with no fork race:

```bash
lldb -- $PWD/dev/install-debug/bin/postgres --single -D "$PGDATA" postgres
(lldb) breakpoint set --name InitPostgres
(lldb) run
```

This sidesteps the per-connection fork problem entirely — there is no
postmaster, no fork, just one process you control end-to-end.

For *post-startup* query debugging, attach to a live backend by PID instead
— see `.claude/commands/pg-attach.md`, which automates the
`SELECT pg_backend_pid()` + `lldb -p <pid>` flow.

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

## Cross-references

- `.claude/skills/debugging/SKILL.md` — attach lldb/gdb to a backend after this skill gets the cluster up.
- `.claude/skills/psql/SKILL.md` — connect to the cluster this skill started.
- `.claude/skills/testing/SKILL.md` — run pg_regress / isolation / TAP against this build.
- `.claude/skills/error-handling/SKILL.md` — interpret `Assert()` triggers and `ereport()` output produced by a cassert build.
- `.claude/commands/setup-pg.md`, `.claude/commands/pg-start.md`, `.claude/commands/pg-restart.md`, `.claude/commands/pg-fresh.md` — slash-command wrappers built on top of this skill.
- Top-level `CLAUDE.md` — `source/` vs `dev/` symlink layout.
