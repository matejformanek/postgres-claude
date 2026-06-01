# session.c

- **Source path:** `source/src/backend/access/common/session.c`
- **Lines:** 208
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `session.h`, `utils/typcache.c` (the one current consumer of the shared registry), `storage/ipc/dsm.c`, `utils/mmgr/dsa.c`.

## Purpose

Encapsulates "user session" state that must be SHARED between the leader and parallel workers. Currently only one thing rides on it: the shared typmod registry for ephemeral record types (so that `BlessTupleDesc`-style typmods assigned by the leader resolve correctly inside workers). The framework anticipates becoming the place to plug in connection pooling. [from-comment, session.c:1-19]

## Top-of-file comment

> "Encapsulation of user session. This is intended to contain data that needs to be shared between backends performing work for a client session. In particular such a session is shared between the leader and worker processes for parallel queries. … Currently this infrastructure is used to share: - typemod registry for ephemeral row-types, i.e. BlessTupleDesc etc." [from-comment, session.c:3-14]

## Public surface

- `InitializeSession` (54) — Allocate the per-process `Session` in `TopMemoryContext`. Called once early in backend init (see `InitPostgres`).
- `GetSessionDsmHandle` (70) — Lazily create the session-scope DSM segment + DSA area + `SharedRecordTypmodRegistry`. Returns `DSM_HANDLE_INVALID` if `DSM_CREATE_NULL_IF_MAXSEGMENTS` triggers (so parallel query can degrade gracefully). The segment is `dsm_pin_mapping`-ed: it persists for the rest of the backend's life.
- `AttachSession` (155) — Called in workers; `dsm_attach(handle)`, walks the shm_toc, attaches to the DSA, attaches to the typmod registry.
- `DetachSession` (201) — Detaches DSM + DSA; runs detach hooks. Anticipated for worker-reuse across sessions (not yet wired in).

## Key invariants

- `CurrentSession` is set up by `InitializeSession`. A backend without a session (e.g. very early postmaster startup) sees `CurrentSession == NULL` and cannot use parallel-shareable session state. [verified-by-code, session.c:48-57]
- The session DSM segment is allocated lazily on first need (first parallel query touching shared record types). [verified-by-code, session.c:82-110]
- Both DSM and DSA mappings are pinned (`dsm_pin_mapping`, `dsa_pin_mapping`) so they live for the rest of the backend regardless of ResourceOwner cleanup. [verified-by-code, session.c:139-141, 187-188]
- The TOC magic (`0xabb0fbc9`) and two key constants (`SESSION_KEY_DSA`, `SESSION_KEY_RECORD_TYPMOD_REGISTRY`) are the contract between leader and workers. [verified-by-code, session.c:30-45]
- `SESSION_DSA_SIZE = 0x30000` (~192 KB) is the initial backing for the DSA; it can grow via DSM segments. [verified-by-code, session.c:39]

## Cross-references

- `InitializeSession` is called from `InitPostgres` (per `git grep`).
- `typcache.c::assign_record_type_typmod` (and friends) is the sole user of the shared record-type registry today.
- `parallel.c` uses `GetSessionDsmHandle` when launching workers and `AttachSession` from worker startup.

## Open questions

- Whether the "anticipated connection-pooling" use case has any concrete code paths today — comment says no. [unverified]

## Confidence tag tally
`[verified-by-code]=6 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
