---
description: Start the ASan/UBSan dev cluster at dev/data-asan/. initdb on first run. Sets ASAN_OPTIONS / UBSAN_OPTIONS appropriately for macOS.
---

# pg-start-asan

Lifecycle for the sanitizer build profile. Sibling to `/pg-start`.

## What to run

From the project root:

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

## Coexisting with the debug cluster

`/pg-start` owns port 5432; `/pg-start-asan` defaults to port 5433.
Socket dir is `/tmp` for both, so the sockets are
`/tmp/.s.PGSQL.5432` and `/tmp/.s.PGSQL.5433` respectively. Both can run
simultaneously without conflict. Connect with the right `-p`:

```bash
psql -h /tmp -d postgres         # debug cluster (5432, default)
psql -h /tmp -p 5433 -d postgres # asan cluster
```

If you specifically want the asan cluster on 5432 (some test harness
that hard-codes the port), stop the debug cluster first (`/pg-stop`) and
edit `dev/data-asan/postgresql.conf` to drop the `port = 5433` line.

## What to expect when a sanitizer hits

On an ASan hit the backend SIGABRTs. `dev/data-asan/server.log` will
contain something like:

```
==12345==ERROR: AddressSanitizer: heap-use-after-free on address 0x...
READ of size 8 at 0x... thread T0
    #0 0x... in palloc src/backend/utils/mmgr/mcxt.c:1234:5
    #1 0x... in ExecProject ...
...
```

Frame numbers map directly to source file:line — no `addr2line` needed.

On a UBSan hit the backend SIGABRTs (because `halt_on_error=1`) and the
log carries:

```
src/backend/access/heap/heapam.c:5678:9: runtime error: signed integer
overflow: 2147483647 + 1 cannot be represented in type 'int'
```

The postmaster restarts a fresh backend after either kind of abort, so
your psql session is the only thing that needs reconnecting.

## Worktree note

Same as `/pg-start`: this resolves paths through the `dev/` symlink.
From a worktree without that symlink, either run from main or add
absolute-path symlinks (see `.claude/skills/build-and-run/SKILL.md`).

## Stopping

`/pg-stop` works for either cluster — it reads `$PGDATA`, so:

```bash
PGDATA=$PWD/dev/data-asan /pg-stop
```

Or just:

```bash
PATH=$PWD/dev/install-asan/bin:$PATH pg_ctl -D $PWD/dev/data-asan stop -m fast
```
