---
description: initdb if needed, then start the dev PG cluster via pg_ctl. Prints the connection string.
---

# pg-start

Start the dev cluster at `dev/data-debug/` using the binaries built by
`/setup-pg` into `dev/install-debug/`.

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"

# 1. initdb only on first run
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" --locale=C --encoding=UTF8
fi

# 2. start (idempotent — pg_ctl status returns 3 if not running, 0 if running)
if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo "postmaster already running"
else
  pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start
fi

# 3. tell user how to connect
echo "Cluster: $PGDATA"
echo "Connect: psql -h /tmp -d postgres"
echo "Log:     $PGDATA/server.log"
```

## Socket directory

On macOS the postmaster's default Unix socket directory is `/tmp` (verified
in this environment via `SHOW unix_socket_directories` → `/tmp`). That's
what `initdb` puts in the freshly written `postgresql.conf` on this OS, so
`psql -h /tmp` is the right invocation. On Linux it would be `/var/run/postgresql`
or `/tmp` depending on distro — check `postgresql.conf` if in doubt.

## After running

Tell the user:

- The connection string they should use: `psql -h /tmp -d postgres`
- Server log is at `dev/data-debug/server.log`.
- Suggest `/pg-stop` to shut down cleanly; `/pg-restart` to bounce.

## Worktree note

All `/pg-*` commands resolve paths through the `dev/` symlink at the
postgres-claude repo root. If you're inside a `.claude/worktrees/<name>/`
worktree and `dev/` doesn't exist, either run this command from main, or
add absolute-path symlinks per-worktree:

```bash
ln -s /Users/matej/Work/postgres/postgresql-dev dev
ln -s /Users/matej/Work/postgres/postgresql     source
```

See `.claude/skills/build-and-run/SKILL.md` "Running these from a git
worktree" for details.

## Troubleshooting

- **`initdb: error: directory "..." exists but is not empty`**: a previous half-
  initialized run. `rm -rf dev/data-debug` and try again.
- **`pg_ctl: could not start server`**: read `dev/data-debug/server.log` —
  usually a port conflict (5432 in use) or stale `postmaster.pid`.
  - Port: another PG already running. Stop it, or set `port = 5433` in
    `dev/data-debug/postgresql.conf`.
  - Stale PID: `rm dev/data-debug/postmaster.pid` (only when *certain* no
    postmaster is alive — check `ps aux | grep postgres`).
- **`initdb` complains about locale on macOS**: we already pass `--locale=C`
  to sidestep system-locale weirdness.
