---
description: Nuclear reset — wipe and re-clone the mutable dev tree from the read-only reference. Destructive — requires --yes.
---

# pg-reclone-dev

Most-destructive option. Wipes the entire mutable `postgresql-dev/` tree
(build artifacts, data dir, local branches, uncommitted edits — everything)
and re-clones it from the read-only reference at `../postgresql/`.

Use this when:
- You've made a mess of the dev clone you can't unwind.
- Local branches/refs are tangled.
- The build system is in an unrecoverable state.

If you only need a clean cluster (not a clean tree), use `/pg-fresh` instead.

## Confirm-before-destruct

```bash
if [ "$1" != "--yes" ]; then
  echo "About to delete /Users/matej/Work/postgres/postgresql-dev/ entirely"
  echo "and re-clone it from /Users/matej/Work/postgres/postgresql/."
  echo "All uncommitted changes, local branches, and build artifacts will be lost."
  echo "Re-invoke as \`/pg-reclone-dev --yes\` to proceed."
  exit 0
fi
```

## What to run

```bash
set -e
cd /Users/matej/Work/postgres/

# 1. Stop the postmaster if it's running
if [ -d postgresql-dev/data-debug ] && \
   postgresql-dev/install-debug/bin/pg_ctl -D postgresql-dev/data-debug status >/dev/null 2>&1; then
  postgresql-dev/install-debug/bin/pg_ctl -D postgresql-dev/data-debug stop -m fast || true
fi

# 2. Wipe the dev clone
rm -rf postgresql-dev

# 3. Re-clone from the read-only reference (no hardlinks → fully independent .git)
git clone --no-hardlinks postgresql postgresql-dev

# 4. Set up remotes:
#    - origin → upstream PG (so `git pull` from dev pulls from real upstream)
#    - local  → the local reference at ../postgresql (for cheap fetches)
cd postgresql-dev
git remote remove origin 2>/dev/null || true
git remote add origin https://git.postgresql.org/git/postgresql.git
git remote add local /Users/matej/Work/postgres/postgresql

# 5. Local-only excludes (don't pollute upstream .gitignore)
mkdir -p .git/info
cat >> .git/info/exclude <<'EOF'
.claude/
CLAUDE.md
build-debug/
install-debug/
data-debug/
EOF

echo ""
echo "Re-clone complete at /Users/matej/Work/postgres/postgresql-dev/"
echo "Next steps:"
echo "  1. /setup-pg     # configure + build + install + reinstall pre-commit hook"
echo "  2. /pg-start     # initdb + start the cluster"
```

The re-clone wipes `dev/.git/hooks/`, so the pg-precommit hook is gone
until `/setup-pg` re-runs `/pg-install-hooks` for you.

## After running

The dev clone is now a fresh copy of upstream master with:
- No build artifacts (`build-debug/`, `install-debug/` gone — `/setup-pg` rebuilds).
- No data dir (`data-debug/` gone — `/pg-start` re-initdbs).
- `origin` pointing at real upstream PG, `local` pointing at the reference clone.
- `.git/info/exclude` set so meta files don't show up as untracked.

The `source/` symlink in the pg-claude repo is unaffected — it points at
`../postgresql/`, not `../postgresql-dev/`.

## Troubleshooting

- **`git clone` is slow**: it shouldn't be — `--no-hardlinks` against a local
  path still uses local file copies, typically a few seconds. If it stalls,
  check disk space (`df -h .`).
- **`fatal: destination path 'postgresql-dev' already exists`**: the `rm -rf`
  above failed. Check for processes holding files open
  (`lsof +D postgresql-dev`), kill them, and retry.
- **postmaster wouldn't stop in step 1**: `pkill -9 postgres` then re-run.
  The `rm -rf` won't care once processes are gone.
