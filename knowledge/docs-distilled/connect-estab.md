---
source_url: https://www.postgresql.org/docs/current/connect-estab.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §52.2: How Connections Are Established

The "process per user" model and the postmaster fork — the single most
load-bearing fact about PG's architecture, and the reason the dev loop here warns
"the backend pid is fresh per psql connect."

## Process-per-user [from-docs]

- PostgreSQL is a **"process per user" client/server** system: *"every client
  process connects to exactly one backend process."* There is no thread pool and
  no shared address space between backends. [from-docs]
- The **postmaster** is the supervisor: it listens on a TCP/IP port (and Unix
  socket) and, on each incoming connection request, **spawns (forks) a new backend
  process**. *"Since we do not know ahead of time how many connections will be
  made,"* the postmaster forks on demand rather than pre-allocating. [from-docs]
  [verified-by-code, source/src/backend/postmaster/postmaster.c — `BackendStartup`
  / fork path; via knowledge/subsystems/storage-ipc.md]

## Coordination is via shared memory + semaphores [from-docs]

- Because backends are separate processes, they coordinate *"using semaphores and
  shared memory to ensure data integrity throughout concurrent data access."*
  Shared memory (buffers, lock tables, PGPROC array) is the **only** shared state;
  everything else is process-private. [from-docs]
  [verified-by-code, source/src/backend/storage/ipc/ — shmem + the per-backend
  PGPROC; via knowledge/data-structures/pgproc-fields.md]

## After the fork [from-docs]

- The client sends queries as **plain text** — *"there is no parsing done in the
  client."* The forked backend **parses, plans, executes, and returns rows** over
  the connection. The client need only speak the wire protocol (Chapter 54);
  libpq is the common C implementation, but independent ones (JDBC, etc.) exist.
  [from-docs]

## Why this matters for hacking here [inferred]

- **The backend PID is fresh on every connect.** To attach a debugger you must
  connect first, find the new backend's PID (`pg_backend_pid()` /
  `pg_stat_activity`), *then* attach — there is no long-lived worker to pre-attach
  to. This is exactly the footgun the `/pg-attach` command and the `debugging`
  skill exist to solve. [inferred from the fork model]
- Per-backend memory contexts, GUC state, and catalog caches are **not shared**;
  a config change or a `DISCARD` affects only the one backend. [inferred]

## Links into corpus

- [[knowledge/architecture/process-model.md]] — the full postmaster/backend/
  auxiliary-process picture.
- [[knowledge/subsystems/storage-ipc.md]] — the shared-memory + semaphore
  machinery backends coordinate through.
- [[knowledge/data-structures/pgproc-fields.md]] — the per-backend PGPROC slot in
  shared memory.
- [[knowledge/docs-distilled/protocol-flow.md]] — the startup-packet +
  authentication handshake this chapter only alludes to.
- [[knowledge/docs-distilled/query-path.md]] — what the forked backend does next.

## Gaps / follow-ups

- The chapter omits the **startup packet** and **authentication** mechanics
  (deferred to protocol-flow / sasl-authentication, both already distilled) and
  does not state the explicit process-vs-thread rationale — that argument lives in
  pgsql-hackers lore, not this page.
