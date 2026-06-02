---
description: Hold a backend open, look up its PID via pg_stat_activity, and print the lldb attach command + useful breakpoints. Solves the per-connection fork-model footgun.
---

# pg-attach

PostgreSQL uses a per-connection fork model: every `psql` session spawns a
fresh backend process. To debug backend code you have to attach to the *right*
PID — the one serving an open psql connection.

**The naive recipe doesn't work.** A one-shot
`psql -tAc 'SELECT pg_backend_pid()'` closes the connection immediately,
so the backend you "got the PID of" is already dead by the time you read
the output. You need a **held** backend.

## What to run

From the project root (`/Users/matej/Work/postgres/postgres-claude/`):

```bash
export PATH="$PWD/dev/install-debug/bin:$PATH"

# Verify the postmaster is up
if ! pg_ctl -D "$PWD/dev/data-debug" status >/dev/null 2>&1; then
  echo "Postmaster not running. Start it with /pg-start first."
  exit 1
fi

# 1. Open a backend that holds its connection open for 5 minutes,
#    tagged with a recognizable application_name so we can find it.
PGAPPNAME=pgattach psql -h /tmp -d postgres -X \
  -c 'SELECT pg_sleep(300);' >/dev/null 2>&1 &
HELD_BG=$!

# 2. Give libpq a moment to register the backend in pg_stat_activity.
sleep 0.5

# 3. Look up the backend PID via the application_name tag.
PID=$(psql -h /tmp -d postgres -tAc \
  "SELECT pid FROM pg_stat_activity WHERE application_name='pgattach' LIMIT 1")

if [ -z "$PID" ]; then
  echo "Could not get backend PID — is the cluster reachable on /tmp?"
  kill $HELD_BG 2>/dev/null
  exit 1
fi

echo "Held backend PID: $PID"
echo "(Held by background psql; stays alive ~5 minutes or until you kill $HELD_BG.)"
echo ""
echo "Attach with:"
echo "  lldb -p $PID"
echo ""
echo "When done, release the held backend:"
echo "  kill $HELD_BG"
```

The backend parked inside `pg_sleep` is sitting in a `WaitLatch` loop —
ready for breakpoints on the code paths you actually care about. To
exercise a code path, set your breakpoint first, then from a SECOND psql
on a SECOND connection, run the SQL that triggers it. (The held backend's
session is asleep — you can't run new queries on it.)

## Useful breakpoints (lldb)

Once attached, inside `(lldb)`:

```
# Silence latch wakeup noise FIRST — every continue otherwise lands in the handler.
pro hand -p true -s false SIGUSR1

breakpoint set --name exec_simple_query
breakpoint set --name ExecutorRun
breakpoint set --name errfinish        # catches every ereport()
continue
```

- `exec_simple_query` — entry point for any text-protocol query (`tcop/postgres.c`).
- `ExecutorRun` — the executor's per-statement entry (`executor/execMain.c`).
- `errfinish` — every error report goes through here; filter on
  `edata->elevel >= 21` to catch ERROR+ only.

See `.claude/skills/debugging/SKILL.md` for the full breakpoint reference
(`§5` for the table; `§5.1` for the errfinish pattern).

## The `pg_usleep` waitpoint pattern

Some interesting code runs *before* you can possibly attach (startup, recovery,
early backend init). To catch it, add a sleep in the source and rebuild:

```c
/* in the code path you want to catch */
elog(LOG, "WAITPOINT pid=%d sleeping 30s", MyProcPid);
pg_usleep(30 * 1000000L);  /* 30 seconds */
```

Then `/setup-pg` to rebuild, `/pg-start`, watch `dev/data-debug/server.log` for
the WAITPOINT line with PID, and `lldb -p <pid>` within the 30s window.

For more advanced waitpoint techniques (single-user mode, `PGOPTIONS="-W N"`),
see `.claude/skills/debugging/SKILL.md` §3 and §4.

## macOS note

`lldb` is the right tool on macOS — `gdb` works but needs codesigning gymnastics
the system tooling doesn't ship with. On Linux, `gdb -p <pid>` is the equivalent.

## Worktree note

This command resolves paths through the `dev/` symlink at the postgres-claude
repo root. If you're inside a `.claude/worktrees/<name>/` worktree and `dev/`
doesn't exist, either run this command from main, or add absolute-path
symlinks per-worktree:

```bash
ln -s /Users/matej/Work/postgres/postgresql-dev dev
ln -s /Users/matej/Work/postgres/postgresql     source
```

See `.claude/skills/build-and-run/SKILL.md` "Running these from a git
worktree" for details.

## Troubleshooting

- **`error: attach failed: Operation not permitted`**: macOS SIP / hardened
  runtime. Either run lldb under sudo (`sudo lldb -p $PID`) or ensure the
  postgres binary you built isn't hardened (debug builds normally aren't).
- **Held backend disappears before you attach**: the 5-minute `pg_sleep`
  expired, or another agent terminated it. Re-run `/pg-attach`.
- **Breakpoint never hits**: you may have attached to the postmaster (which
  forks for each connection) instead of a backend. Verify the PID via
  `ps -p $PID -o command=` — it should read `postgres: <user> postgres
  /tmp 127.0.0.1 idle` or similar; if it just reads `postgres` with no
  per-backend tail, you're on the postmaster.
- **`SELECT pid FROM pg_stat_activity WHERE application_name='pgattach'`
  returns empty**: the env var `PGAPPNAME` didn't propagate. Some shells
  strip `PGAPPNAME` for backgrounded processes — try `env PGAPPNAME=pgattach
  psql ...` instead of the inline assignment. (psql's own `--set` is for
  psql variables and does NOT set the libpq application_name.)
