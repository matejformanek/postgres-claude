---
description: Tail the dev cluster's server.log with optional noise filtering.
---

# pg-tail-log

Follow `dev/data-debug/server.log` live.

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
# Last 100 lines, then follow. -F survives log rotation / truncation.
tail -F --lines=100 "$PWD/dev/data-debug/server.log"
```

(macOS BSD `tail` accepts `-F` and `-n 100` — same effect; `--lines=100` is
the GNU long form and works under coreutils if installed.)

## Strip noisy LOG: prefixes

Most lines start with `LOG:` for routine info. To focus on warnings/errors:

```bash
# Hide plain LOG: lines, keep WARNING/ERROR/FATAL/PANIC and stack traces
tail -F --lines=100 "$PWD/dev/data-debug/server.log" | grep -v "^[0-9-]* [0-9:.]* [A-Z]* \[[0-9]*\] LOG:"
```

Or with `--line-buffered` to keep output flowing:

```bash
tail -F --lines=100 "$PWD/dev/data-debug/server.log" \
  | grep --line-buffered -E "WARNING|ERROR|FATAL|PANIC|STATEMENT"
```

## Where the log comes from

`/pg-start` invokes `pg_ctl ... -l "$PGDATA/server.log" start`, so all
postmaster + backend stderr funnels into that one file. There is no
rotation in this dev setup — the file grows forever. If it gets unwieldy:

```bash
# Truncate (postmaster keeps writing to the same fd, file restarts at 0)
: > "$PWD/dev/data-debug/server.log"
```

## Troubleshooting

- **`tail: ... server.log: No such file or directory`**: cluster has never
  been started. Run `/pg-start` first.
- **No output for a long time**: the cluster is healthy and idle. Try a
  query in another terminal (`/pg-psql`, then `SELECT 1;`) to see normal
  log flow, or bump `log_statement = 'all'` in `postgresql.conf` for a
  noisier view.
