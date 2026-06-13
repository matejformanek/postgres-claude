---
description: initdb if needed, then start the dev PG cluster via pg_ctl. Default profile is `build-debug` on port 5432; pass `--asan` to start the ASan/UBSan profile on port 5433 instead. Prints the connection string.
---

# pg-start

Start the dev cluster from the build profile of your choice. Default
is `build-debug` (the `cassert + debug` build under `dev/install-debug/`
and `dev/data-debug/`); `--asan` switches to the AddressSanitizer +
UndefinedBehaviorSanitizer build under `dev/install-asan/` and
`dev/data-asan/`.

Both profiles can coexist — the debug cluster owns port 5432, the asan
cluster owns port 5433. Socket dir is `/tmp` for both.

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

### Debug profile (default)

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

### ASan profile (when invoked as `/pg-start --asan`)

```bash
# Use the asan install + a separate data dir
export PATH="$PWD/dev/install-asan/bin:$PATH"
export PGDATA="$PWD/dev/data-asan"

# Runtime sanitizer knobs:
# - detect_leaks=0 because LSan is not supported on Darwin (would error).
# - abort_on_error=1 makes the backend SIGABRT immediately on a hit;
#   postmaster restarts a fresh one.
# - detect_stack_use_after_return=1 catches another whole class of UAF.
# - print_stacktrace=1 puts full backtraces in the server log on every hit.
export ASAN_OPTIONS="abort_on_error=1:detect_leaks=0:detect_stack_use_after_return=1:print_stacktrace=1"
export UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1"

# 1. initdb only on first run
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" --locale=C --encoding=UTF8
fi

# 2. Default port: 5433 (debug cluster owns 5432). Idempotent.
grep -q "^port" "$PGDATA/postgresql.conf" || echo "port = 5433" >> "$PGDATA/postgresql.conf"

# 3. Don't double-start
if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  echo "asan postmaster already running on $PGDATA"
else
  pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" start
fi

echo "ASan cluster: $PGDATA"
echo "Connect:  PATH=\"$PWD/dev/install-asan/bin:\$PATH\" psql -h /tmp -p 5433 -d postgres"
echo "Log:      $PGDATA/server.log"
```

## Socket directory

On macOS the postmaster's default Unix socket directory is `/tmp`. That's
what `initdb` puts in the freshly written `postgresql.conf` on this OS, so
`psql -h /tmp` is the right invocation for both profiles. On Linux it
would be `/var/run/postgresql` or `/tmp` depending on distro — check
`postgresql.conf` if in doubt.

## Coexisting clusters

Debug owns port 5432; ASan owns port 5433. Sockets are
`/tmp/.s.PGSQL.5432` and `/tmp/.s.PGSQL.5433` respectively. Both can
run simultaneously without conflict. Connect with the right `-p`:

```bash
psql -h /tmp -d postgres            # debug cluster (5432, default)
psql -h /tmp -p 5433 -d postgres    # asan cluster
```

If you specifically want the ASan cluster on 5432 (some test harness
that hard-codes the port), stop the debug cluster first (`/pg-stop`) and
edit `dev/data-asan/postgresql.conf` to drop the `port = 5433` line.

## What to expect when a sanitizer hits (ASan profile only)

On an ASan hit the backend SIGABRTs. `dev/data-asan/server.log` will
contain something like:

```
==12345==ERROR: AddressSanitizer: heap-use-after-free on address 0x...
READ of size 8 at 0x... thread T0
    #0 0x... in palloc src/backend/utils/mmgr/mcxt.c:1234:5
    #1 0x... in ExecProject ...
```

Frame numbers map directly to source `file:line` — no `addr2line`
needed. The postmaster restarts a fresh backend after the abort, so
your psql session is the only thing that needs reconnecting.

On a UBSan hit (also SIGABRT because `halt_on_error=1`) the log
carries:

```
src/backend/access/heap/heapam.c:5678:9: runtime error: signed integer
overflow: 2147483647 + 1 cannot be represented in type 'int'
```

## After running

Tell the user:

- The connection string they should use (per profile — see above).
- Server log location.
- Suggest `/pg-stop` to shut down cleanly; `/pg-restart` to bounce.

## Stopping

`/pg-stop` works for either cluster — it reads `$PGDATA`. For the
ASan cluster specifically:

```bash
PGDATA=$PWD/dev/data-asan /pg-stop
```

Or:

```bash
PATH=$PWD/dev/install-asan/bin:$PATH pg_ctl -D $PWD/dev/data-asan stop -m fast
```

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

- **`initdb: error: directory "..." exists but is not empty`** — a
  previous half-initialized run. `rm -rf dev/data-{debug,asan}` (the
  appropriate one) and try again.
- **`pg_ctl: could not start server`** — read the server log under the
  matching `$PGDATA`. Usually a port conflict or a stale `postmaster.pid`.
  - Port: another PG already running. Stop it, or set `port = 5433`
    in the debug profile's `postgresql.conf` if you want to shift it.
  - Stale PID: `rm $PGDATA/postmaster.pid` (only when *certain* no
    postmaster is alive — check `ps aux | grep postgres`).
- **`initdb` complains about locale on macOS** — we already pass
  `--locale=C` to sidestep system-locale weirdness.
