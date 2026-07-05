---
source_url: https://www.postgresql.org/docs/current/server-shutdown.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§19.5 Shutting Down the Server"
maps_to_skills: [debugging, build-and-run]
maps_to_corpus: [knowledge/files/src/backend/postmaster/postmaster.c.md, knowledge/docs-distilled/wal-reliability.md, knowledge/subsystems/access-transam.md]
---

# Shutting down the server — the three shutdown modes (§19.5)

Signals go to the **postmaster**, which relays them; the signal chosen picks
how much in-flight work is preserved vs. aborted.

## Non-obvious claims

- **Signal → mode mapping (sent to the postmaster, not backends):**
  - **SIGTERM = Smart Shutdown** — refuse new connections, let existing sessions
    finish naturally (and, on a primary, wait for any online backup to finish);
    shut down only once all sessions end.
  - **SIGINT = Fast Shutdown** (the recommended mode) — refuse new connections,
    send SIGTERM to each backend so it aborts its current transaction and exits,
    wait for them, then shut down cleanly.
  - **SIGQUIT = Immediate Shutdown** — send SIGQUIT to every child, exit with no
    clean shutdown; **next start does crash recovery (WAL replay)**. If a child
    doesn't die within 5 s it gets SIGKILL. `[from-docs]`
  - Verified: `pmdie()` switches on exactly these three signals.
    `[verified-by-code]` `source/src/backend/postmaster/postmaster.c:2080`
    (SIGTERM/Smart), `:2084` (SIGINT/Fast), `:2088` (SIGQUIT/Immediate).
- **`pg_ctl stop -m {smart|fast|immediate}`** is the friendly wrapper for those
  three signals; the raw form is `kill -INT $(head -1 $PGDATA/postmaster.pid)`.
  `[from-docs]`
- **Never SIGKILL the postmaster.** It "will prevent the server from releasing
  shared memory and semaphores," and because SIGKILL can't be relayed, orphan
  child backends may need manual killing — and the stale IPC can corrupt the next
  start. `[from-docs]`
- **A single backend dying uncleanly (e.g. SIGKILL) is treated as a crash:** the
  postmaster restarts the whole cluster through crash recovery to guarantee
  shared-memory consistency — one killed backend ⇒ every session dropped.
  `[from-docs]` (this is why `SIGQUIT`, not SIGKILL, is the backend panic signal.)
- **Terminate one session cleanly** with `pg_terminate_backend(pid)` (or SIGTERM
  to that backend) — no cluster-wide restart. `[from-docs]`

## Links into corpus

- [[knowledge/files/src/backend/postmaster/postmaster.c.md]] — `pmdie()` and the
  child-reaping / restart-after-crash state machine.
- [[knowledge/docs-distilled/wal-reliability.md]] — why an immediate shutdown is
  safe (WAL replay reconstructs a consistent state).
- [[knowledge/subsystems/access-transam.md]] — crash recovery / redo path the
  immediate mode forces.
</content>
