---
description: First-time walkthrough — install PostgreSQL from source for hacking. Clones both repos, installs Homebrew deps, runs the verified build, starts the cluster.
---

# init-pg-dev

Interactive walkthrough for setting up a local PostgreSQL development environment
from scratch. Run this when you have **nothing yet** — no clone, no build, no
cluster. By the end you'll have a working `psql` connected to a debug build of
PG and the pg-claude meta repo wired into it.

If you already have a PG clone elsewhere on disk and want to wire pg-claude into
it instead of creating new clones, use `/link-claude-corpus` instead.

## What this command does

Run these steps interactively with the user. After each step, confirm success
before moving on. Don't be a robot — explain each step in one short sentence,
then run it. If anything fails, stop and surface the error.

### Step 1 — Pick a workspace root

Ask the user where to put the two upstream clones. Default: the parent of
`postgres-claude/`. So if `postgres-claude/` lives at `/Users/matej/Work/postgres/postgres-claude/`,
the workspace root is `/Users/matej/Work/postgres/` and the clones will land at
`/Users/matej/Work/postgres/postgresql/` and `/Users/matej/Work/postgres/postgresql-dev/`.

```bash
WORKSPACE_ROOT="$(cd "$PWD/.." && pwd)"
echo "Workspace root: $WORKSPACE_ROOT"
echo "Postgres clones will be created here:"
echo "  $WORKSPACE_ROOT/postgresql       (read-only reference)"
echo "  $WORKSPACE_ROOT/postgresql-dev   (mutable test field)"
echo "OK to proceed? (yes/no)"
```

### Step 2 — Check Homebrew toolchain

Verify the build deps. On macOS the canonical set is:

```bash
brew install meson ninja bison flex icu4c openssl@3 readline zlib lz4 zstd libxml2 libxslt
```

For each, run `brew list <pkg>` and report missing ones. Offer to `brew install`
the missing set in one command. **Don't auto-install** without asking — Homebrew
can be slow and the user may want to opt out of optionals.

Mandatory: `meson`, `ninja`, `bison` (Homebrew bison — macOS system bison is too
old), `icu4c`. Everything else is strongly recommended but PG will configure
without them.

Also check `bison` is on PATH at a version ≥ 3.0:
```bash
bison --version
```
If the macOS system bison shows up, prompt the user to add the Homebrew bison
to PATH for this session and tell them to persist it:
```bash
export PATH="/opt/homebrew/opt/bison/bin:$PATH"
```

### Step 3 — Clone upstream PostgreSQL (read-only reference)

If `$WORKSPACE_ROOT/postgresql/` already exists, skip. Otherwise:

```bash
cd "$WORKSPACE_ROOT"
git clone https://git.postgresql.org/git/postgresql.git postgresql
```

Then `cd postgresql && git log -1 --format='%H %s'` to confirm.

Add the local-exclude so `.claude/` and `CLAUDE.md` never leak into an upstream patch:
```bash
cat >> postgresql/.git/info/exclude <<'EOF'

# pg-claude meta repo artifacts — never commit upstream
.claude/
CLAUDE.md
build-debug/
install-debug/
data-debug/
EOF
```

### Step 4 — Clone the mutable dev field

Faster than re-cloning upstream — use `--no-hardlinks` against the local reference:

```bash
cd "$WORKSPACE_ROOT"
git clone --no-hardlinks postgresql postgresql-dev
cd postgresql-dev
git remote set-url origin https://git.postgresql.org/git/postgresql.git
git remote add local "$WORKSPACE_ROOT/postgresql"
```

Same `.git/info/exclude` block.

### Step 5 — Wire the symlinks into postgres-claude/

```bash
cd /Users/matej/Work/postgres/postgres-claude  # this repo
# Skip if symlinks already exist
[ -L source ] || ln -s ../postgresql source
[ -L dev ]    || ln -s ../postgresql-dev dev
```

Verify:
```bash
ls source/src/backend/storage/buffer/README   # must resolve
ls dev/src/backend/storage/buffer/README      # must resolve
```

### Step 6 — Build PG (debug, with asserts)

Hand off to `/setup-pg`. That command is already verified end-to-end (see
`.claude/skills/build-and-run/SKILL.md`):

```bash
meson setup dev/build-debug dev \
  --buildtype=debug \
  -Dcassert=true \
  -Ddebug=true \
  -Dprefix=$PWD/dev/install-debug
ninja -C dev/build-debug
ninja -C dev/build-debug install
```

Expected: ~15s on Apple Silicon, ~1 min on slower hardware. If meson fails,
walk through the error with the user — the most common ones are documented in
`.claude/commands/setup-pg.md` Troubleshooting.

### Step 7 — initdb + start + verify

Hand off to `/pg-start`:

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"
initdb -D "$PGDATA" --locale=C --encoding=UTF8
pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start
```

Verify with a real query:
```bash
psql -h /tmp -d postgres -c 'SELECT version();'
```

Expected output includes `PostgreSQL 19devel` (or whatever master is at).

### Step 8 — Optional: run the regression suite

Ask the user if they want to confirm the build by running the headline tests
(~34s on M-series):

```bash
meson test -C dev/build-debug --suite setup --suite regress --num-processes 4
```

This is where the `--suite setup` gotcha bites — don't omit it.

### Step 9 — Report and recap

Print a final summary:

- Source reference at: `$WORKSPACE_ROOT/postgresql/` (read-only)
- Dev clone at: `$WORKSPACE_ROOT/postgresql-dev/` (mutable; safe to wipe via `/pg-reclone-dev`)
- Cluster running at port 5432, socket dir `/tmp`
- Open psql with `/pg-psql`
- Stop with `/pg-stop`
- Restart with `/pg-restart`
- Full reset (keep build, wipe data): `/pg-fresh --yes`
- Nuclear reset (rebuild from scratch): `/pg-reclone-dev --yes` then `/setup-pg` then `/pg-start`

## Troubleshooting

- **`brew: command not found`** — install Homebrew first: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`.
- **`git clone https://git.postgresql.org/git/postgresql.git` is slow** — the upstream PG repo is ~3 GB and on a sometimes-flaky mirror. Be patient or use a mirror (`https://github.com/postgres/postgres.git` is the canonical mirror).
- **`meson setup` says missing perl** — install Homebrew perl: `brew install perl`. PG needs perl ≥ 5.14 for code generation (Catalog.pm, gen_node_support.pl etc.).
- **`psql: connection refused`** — check `dev/data-debug/server.log` for the actual error. Most common: port 5432 already taken by an existing PG install; either stop that one or set `port = 5433` in `dev/data-debug/postgresql.conf` and `/pg-restart`.
