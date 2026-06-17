---
description: First-time PostgreSQL meson setup + build + install into dev/{build,install}-debug. Builds inside the mutable dev/ clone — never touches the read-only source/ reference.
---

# setup-pg

One-shot configure + build + install for the mutable dev clone at `dev/`.
Idempotent: if `dev/build-debug/build.ninja` already exists, skip the meson
setup step. Pass `--force` to wipe and reconfigure from scratch.

**Repo split reminder:** `source/` is the read-only reference (kept exactly
in sync with upstream `master`, used for code citations). `dev/` is the
mutable playground — that's where every build artifact lives and where you
can safely edit, rebuild, or wipe-and-reclone.

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
# 1. Configure (skip if build.ninja exists, unless --force was passed)
if [ -f dev/build-debug/build.ninja ] && [ "$1" != "--force" ]; then
  echo "build-debug already configured; skipping meson setup (use --force to reconfigure)"
else
  rm -rf dev/build-debug   # only if --force or no build.ninja
  meson setup dev/build-debug dev \
    --buildtype=debug \
    -Dcassert=true \
    -Ddebug=true \
    -Dprefix=$PWD/dev/install-debug
fi

# 2. Build (incremental; ninja decides what to redo)
ninja -C dev/build-debug

# 3. Install into dev/install-debug/
ninja -C dev/build-debug install

# 4. Install the pg-precommit git hook into dev/.git/hooks/pre-commit.
#    Idempotent; safe to re-run.
/pg-install-hooks
```

Expected wall-clock on Apple Silicon (M-series, debug build): roughly 15s
for a clean build, seconds for an incremental.

## After running

Tell the user:

- The binaries are now under `dev/install-debug/bin/`.
- Suggest adding to PATH for this shell: `export PATH=$PWD/dev/install-debug/bin:$PATH`.
- Suggest `PGDATA=$PWD/dev/data-debug` for the dev cluster.
- The pre-commit hook is now in place (`dev/.git/hooks/pre-commit`):
  format-check + R13-scoped meson test on each commit. Bypass with
  `PG_PRECOMMIT_SCOPE=skip git commit ...` if you need to.
- Next step is `/pg-start` (which will `initdb` on first run).

## Toolchain prerequisites (macOS / Homebrew)

The meson configure step found and used these — verify they exist if setup
fails:

- `meson` (≥ 1.0), `ninja` — `brew install meson ninja`
- `bison` (`brew install bison`; PG needs ≥ 3.0, the system one on macOS is too old)
- `flex` — comes with Command Line Tools
- `icu4c` (`brew install icu4c`) — meson picks it up via the Homebrew pkg-config path
- `openssl`, `readline`, `zlib`, `lz4`, `zstd`, `libxml2`, `libxslt` — all from Homebrew

Optional that PG can do without (verified-absent in this environment, configure
still succeeds): `dtrace`, `gss`, `libnuma`, `liburing`, `llvm`, `selinux`,
`systemd`, `uuid`.

## Build flag rationale

- `--buildtype=debug` (not `debugoptimized`) → readable gdb/lldb backtraces.
- `-Dcassert=true` → enable `Assert()` macros; essential when reading internals.
- `-Ddebug=true` → debug symbols.
- `-Dprefix=$PWD/source/install-debug` → keeps the install local to the worktree.

## Where artifacts land

All inside `dev/` (the mutable clone), not `source/`:

- Build tree: `dev/build-debug/` (gitignored upstream via `build*/`)
- Install tree: `dev/install-debug/` (gitignored upstream via `install*/`)
- Data dir (created later by `/pg-start`): `dev/data-debug/` (excluded
  locally via `postgresql-dev/.git/info/exclude`)

## Troubleshooting

- **Meson can't find bison**: macOS ships an ancient bison. Install via Homebrew
  and `export PATH="/opt/homebrew/opt/bison/bin:$PATH"` before re-running.
- **icu4c not found**: `brew install icu4c` and either re-run `setup` (Homebrew
  shims should resolve it) or pass `PKG_CONFIG_PATH=/opt/homebrew/opt/icu4c/lib/pkgconfig`.
- **Stale build after upstream pull**: `rm -rf dev/build-debug` then re-run.
- **Want a totally fresh dev clone**: from the parent dir `/Users/matej/Work/postgres/`,
  `rm -rf postgresql-dev && git clone --no-hardlinks postgresql postgresql-dev`
  then re-do this command. The dev clone is designed to be disposable.
