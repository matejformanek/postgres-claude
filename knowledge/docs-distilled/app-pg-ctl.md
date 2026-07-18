---
source_url: https://www.postgresql.org/docs/current/app-pg-ctl.html
fetched_at: 2026-07-18
anchor_sha: 03480907e9ff
app: src/bin/pg_ctl/pg_ctl.c
---

# pg_ctl — start, stop, and control a server

Thin lifecycle wrapper over the `postgres` postmaster: it launches the server
detached, reads `postmaster.pid` to poll readiness/shutdown, and signals the
running postmaster for stop/reload/promote/logrotate. Everything reduces to
"launch the binary" or "send the right signal and watch the pidfile."

## Non-obvious claims

- Shutdown mode → signal mapping (the whole reason `-m` exists), code-verified:
  **smart → `SIGTERM`**, **fast → `SIGINT`** (the *default*), **immediate →
  `SIGQUIT`**. The default is `sig = SIGINT` (fast); the `-m` parser overwrites it.
  Fast forcibly disconnects clients and rolls back in-flight transactions but
  still shuts down cleanly; immediate skips the clean shutdown and forces
  crash-recovery on next start.
  `[verified-by-code source/src/bin/pg_ctl/pg_ctl.c:81,2052,2057,2062]`
- `reload` sends `SIGHUP`; `logrotate` sends `SIGUSR1`; `promote` and
  `logrotate` set `sig = SIGUSR1` internally, but **promote actually works by
  dropping a promote *signal file*** in the data dir that the running standby
  detects — not purely by the signal.
  `[verified-by-code source/src/bin/pg_ctl/pg_ctl.c:1234,1307,2450]`
- Readiness/shutdown detection is **entirely via `postmaster.pid`**: on `start`
  with `-w` pg_ctl polls the pidfile until it reports "ready to accept
  connections"; on `stop` it polls until the pidfile is *removed*. There is no
  separate handshake channel. `[from-docs]`
- `-w`/`--wait` is the **default** for `start`/`stop`/`restart`/`promote`/
  `register`; timeout is `-t`/`--timeout` seconds, defaulting to env
  `PGCTLTIMEOUT` or **60 s** if unset. On timeout pg_ctl exits nonzero even
  though the backgrounded operation may still be proceeding.
  `[verified-by-code source/src/bin/pg_ctl/pg_ctl.c:70,77]`
- `restart` **reuses the previous command-line options** by reading
  `postmaster.opts` from the data dir — unless `-o` is given, which *replaces*
  the saved set. This is why a one-off `-o` on start silently persists across a
  later plain `restart`. `[from-docs]`
- `status` exit codes are a stable contract: **0 = running**, **3 = not
  running**, **4 = data dir inaccessible** — scriptable without parsing text.
  `[from-docs]`
- The `kill <signame> <pid>` subcommand is a portable `kill(2)` (mainly for
  Windows where there's no `kill`); it maps names to signals directly
  (`HUP/INT/QUIT/ABRT/KILL/TERM/USR1/USR2`).
  `[verified-by-code source/src/bin/pg_ctl/pg_ctl.c:2078-2092]`
- On start, stdin is redirected to `/dev/null`; on Unix stdout/stderr default to
  pg_ctl's own streams (so you *should* pass `-l logfile`), whereas on Windows
  they go to the terminal. `[from-docs]`
- `-c`/`--core-files` lifts the soft core-file `rlimit` so a crashing backend can
  actually dump core for debugging. `-s`/`--silent` suppresses info messages.
  Windows-only `register`/`unregister` manage the service (`-N` name, `-S
  auto|demand` start type, `-U`/`-P` service account). `[from-docs]`

## Links into corpus

- The postmaster it launches + its signal handling and shutdown state machine:
  `[[knowledge/docs-distilled/app-postgres.md]]`, `[[knowledge/docs-distilled/server-shutdown.md]]`,
  `[[knowledge/docs-distilled/server-start.md]]`, the `process-lifecycle` skill.
- Promote signal-file mechanism + standby end-of-recovery:
  `[[knowledge/docs-distilled/warm-standby-failover.md]]`, `hot-standby.md`.
- `initdb` invoked by `pg_ctl init`: `[[knowledge/docs-distilled/app-initdb.md]]`.
- SIGHUP config reload semantics: `[[knowledge/docs-distilled/runtime-config-custom.md]]`.
