---
description: Open psql against the running dev cluster (psql -h /tmp -d postgres).
---

# pg-psql

Connect to the running dev cluster with the freshly built `psql`.

## What to run

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"

# Verify the postmaster is actually up
if ! pg_ctl -D "$PWD/dev/data-debug" status >/dev/null 2>&1; then
  echo "Postmaster not running. Start it with /pg-start first."
  exit 1
fi

psql -h /tmp -d postgres "$@"
```

## Why `-h /tmp`

PostgreSQL on macOS defaults its Unix socket directory to `/tmp` (this is what
`initdb` writes into `postgresql.conf`'s `unix_socket_directories` setting).
Without `-h /tmp`, `psql` would try `/var/run/postgresql` (the Linux default
baked into `libpq` on some builds) or TCP `localhost`, neither of which is
guaranteed to be listening.

To verify on a running cluster:
```sql
SHOW unix_socket_directories;
```

## Useful one-liners

```bash
# Run a single query and exit
psql -h /tmp -d postgres -c 'SELECT version();'

# Get the backend PID for attaching gdb (per-connection fork model)
psql -h /tmp -d postgres -c 'SELECT pg_backend_pid();'

# Verbose error output
psql -h /tmp -d postgres -v VERBOSITY=verbose
```

## Troubleshooting

- **`psql: error: connection to server on socket "/tmp/.s.PGSQL.5432" failed: No such file`**:
  postmaster isn't running, or it's listening on a different port. Check
  `dev/data-debug/postgresql.conf` for `port = ...` and
  `unix_socket_directories = ...`.
- **`role "matej" does not exist`** (or whatever your username is): on first
  connect with no `-U`, libpq uses your OS username. The default superuser
  created by `initdb` matches the OS user that ran `initdb`, so this normally
  works. If it doesn't: `psql -h /tmp -d postgres -U postgres` may be wrong;
  try `psql -h /tmp -U $(whoami) -d postgres`.
