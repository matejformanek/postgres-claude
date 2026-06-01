---
description: Stop the dev PG cluster (pg_ctl stop -m fast). Idempotent.
---

# pg-stop

Cleanly shut down the dev postmaster.

## What to run

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"
export PGDATA="$PWD/dev/data-debug"

if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" stop -m fast
else
  echo "postmaster not running"
fi
```

`-m fast` = SIGINT to backends, rollback in-flight transactions, no waiting
for clients to disconnect. Good default for dev. Use `-m smart` to wait for
clients, `-m immediate` to SIGQUIT (forces recovery on next start).

## Troubleshooting

- **`pg_ctl: PID file ... does not exist`**: cluster already stopped — the
  idempotency check above should have caught this; if it didn't, the data dir
  may have been wiped.
- **Stuck shutdown**: `pg_ctl -D "$PGDATA" stop -m immediate` then start again
  (will replay WAL on startup).
