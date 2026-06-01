---
description: Restart the dev PG cluster (stop -m fast, then start).
---

# pg-restart

Bounce the postmaster. Equivalent to `/pg-stop` followed by `/pg-start`.

## What to run

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"

# Stop if running
if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" stop -m fast
fi

# Start (assumes initdb already happened — use /pg-start for first run)
pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start

echo "Connect: psql -h /tmp -d postgres"
```

Use after:

- Changing `postgresql.conf` settings that require restart (shared_buffers,
  max_connections, wal_level, …). For SIGHUP-reloadable settings use `pg_ctl
  reload` instead.
- Installing a new shared_preload_libraries extension.
- Re-running `ninja -C dev/build-debug install` with backend code changes
  — restart picks up the new `postgres` binary.

## Troubleshooting

See `/pg-start` and `/pg-stop` troubleshooting sections.
