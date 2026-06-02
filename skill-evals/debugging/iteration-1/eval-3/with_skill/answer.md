# Debugging the early backend startup path (InitPostgres)

Attaching to a forked backend after psql is up is too late for code that runs *before* the backend is ready to accept queries (auth, shmem init, InitPostgres, startup hooks). Per `.claude/skills/debugging/SKILL.md` §3 (lines 67–86), there are three approaches; pick based on *how* early.

## Option A — single-user mode (the right tool for InitPostgres)

`postgres --single` runs the backend without a postmaster and **without forking** — the debugger sees the whole lifetime in one process. This is the canonical way to step through startup/auth code.

```bash
# lldb (macOS)
lldb -- postgres --single -D "$PGDATA" postgres

# gdb (Linux)
gdb --args postgres --single -D "$PGDATA" postgres
```

Once stopped at startup, set your breakpoint and run:

```
(lldb) b InitPostgres
(lldb) run
```

[SKILL.md §3, lines 73–78; verified from `source/doc/src/sgml/ref/postgres-ref.sgml` line 714+ which gives the canonical invocation `postgres --single -D /usr/local/pgsql/data other-options my_database`.]

### Quirks of `--single`

- **Newline terminates a command**, not semicolon (SKILL.md §3, lines 84–86, verified against `postgres-ref.sgml` around line 730). If you're pasting psql-style scripts, pass `-j` to switch to `;\n\n` mode.
- There's no postmaster, no shared-memory coordination with other backends, no autovacuum. So this is for stepping through code, not for reproducing concurrency issues.
- `fprintf(stderr, ...)` in single-user mode goes straight to your controlling terminal (SKILL.md §7, lines 173–174). Handy for ad-hoc tracing while you're already attached.

## Option B — `PGOPTIONS="-W N"` startup delay

If you specifically want to debug a *regular* (forked) backend's early startup — not the path you'd get under `--single` — start the connection with:

```bash
PGOPTIONS="-W 10" psql ...
```

The backend sleeps for 10 seconds right at startup before doing anything. In that window, run `SELECT pg_backend_pid()` (well, you can't yet — instead `ps` for the postgres backend, or have the backend log its PID) and `lldb -p <pid>` (SKILL.md §4, lines 91–94).

Use this when the question is "does the forked-backend path behave differently from `--single`?" — rare, but real for things involving shared-memory attach order.

## Option C — spin-loop waitpoint

For arbitrarily-early code paths (including stuff that runs before `-W` would even take effect, or in short-lived background workers / parallel workers / autovacuum workers where there's no client connection at all), insert a temporary spin loop in the source and rebuild (SKILL.md §4, lines 95–103):

```c
bool wait = true;
elog(LOG, "waiting for debugger, pid=%d", MyProcPid);
while (wait) pg_usleep(1000000L);
```

Trigger the path, find the PID in the server log, `lldb -p <pid>`, then `expr wait = 0` to release. Project slash command `/pg-attach` documents the same pattern under "The `pg_usleep` waitpoint pattern" (lines 59–71). Don't ship the spin loop.

## When to use which

- **`--single` mode** → InitPostgres, GUC bootstrap, shmem init, auth, anything that runs in the bootstrap/standalone path. Single, clean process. This is your default for the question asked.
- **`PGOPTIONS="-W"`** → you specifically need the *forked* backend startup path (the difference matters for shmem-attach, signal handlers).
- **Spin-loop waitpoint** → autovacuum workers, parallel workers, background workers, recovery — code paths with no controlling psql session.

## Other notes

- SKILL.md §10 also points out that some test paths already sleep deliberately (`source/src/backend/access/transam/xlog.c:7707, 7724` retry loops in WAL recovery) and that the TAP test infra has a real waitpoint mechanism (`source/src/test/authentication/t/007_pre_auth.pl` line 38).
- Cross-reference `.claude/skills/build-and-run/SKILL.md` for how the dev cluster's `$PGDATA` is set up — it lives at `dev/data-debug/` in this repo.
