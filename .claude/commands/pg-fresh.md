---
description: Nuke the dev data directory and re-initdb from scratch. Destructive — requires --yes.
---

# pg-fresh

Full reset of the dev cluster's *data dir* (not the build). Stops the
postmaster if running, deletes `dev/data-debug/`, then re-runs the
`/pg-start` flow (which `initdb`s on first run).

This is for "I broke the cluster, just nuke it" — corrupted catalog,
mismatched WAL, broken extension install, etc. Build artifacts in
`dev/build-debug/` and `dev/install-debug/` are **untouched**.

## Confirm-before-destruct

```bash
if [ "$1" != "--yes" ]; then
  echo "About to wipe \`dev/data-debug/\`. Re-invoke as \`/pg-fresh --yes\` to proceed."
  exit 0
fi
```

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"

# 1. Stop the postmaster if it's running
if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" stop -m fast
fi

# 2. Wipe the data dir
rm -rf "$PGDATA"

# 3. Re-initdb + start (mirror of /pg-start)
initdb -D "$PGDATA" --locale=C --encoding=UTF8
pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start

# 4. Confirm
echo "Fresh cluster: $PGDATA"
echo "Connect: psql -h /tmp -d postgres"
```

## After running

The cluster is back to a virgin `initdb` state: only `postgres`, `template0`,
`template1` databases; the default superuser is your OS username. Any test
data, extensions, roles, or schema changes from before are gone.

`/pg-fresh` only wipes the data dir — the `dev/.git/hooks/pre-commit` hook
is untouched. If you re-cloned `dev/` earlier (via `/pg-reclone-dev`),
re-run `/pg-install-hooks` to put the hook back; `/setup-pg` does it
for you on the standard reclone path.

## Troubleshooting

- **`pg_ctl: server does not shut down`**: a backend is stuck. Either
  `pg_ctl stop -m immediate` (forces WAL replay on next start, fine here
  since we're wiping anyway) or `pkill -9 postgres` then proceed.
- **`rm: dev/data-debug/...: Permission denied`**: stale files owned by a
  different user (rare). `sudo rm -rf` only if you're certain.
- **`initdb: directory exists but is not empty`**: the `rm -rf` above
  failed silently. Check `ls -la dev/data-debug/` and remove manually.

## When *not* to use this

If the *binaries* are broken (segfaults, missing symbols), `/pg-fresh` won't
help — you need to rebuild. Use `/setup-pg --force` instead, or
`/pg-reclone-dev` for the nuclear option.
