---
source_url: https://www.postgresql.org/docs/current/libpq-cancel.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.7 — Canceling Queries in Progress (new PG17 async PGcancelConn API vs legacy PGcancel)"
maps_to_skill: wire-protocol
---

# libpq §34.7 — Canceling Queries in Progress

Cancellation is out-of-band: it rides a *separate* connection to the server that
quotes the backend's cancel key (from BackendKeyData sent at startup). PG17 added
a whole new object-based, poll-driven, encryption-respecting API alongside the
legacy one.

## Non-obvious claims

- **The new API opens a brand-new connection per cancel.** `PQcancelCreate(PGconn
  *conn)` returns a `PGcancelConn`; dispatching the request via
  `PQcancelBlocking` or the `PQcancelStart`/`PQcancelPoll` pair "opens a separate
  connection to the server." `PQcancelCreate` at
  `source/src/interfaces/libpq/fe-cancel.c:67`, `PQcancelBlocking` at `:190`,
  `PQcancelStart` at `:204`, `PQcancelPoll` at `:226`. [verified-by-code]
- **`PQcancelPoll` reuses the `PQconnectPoll` loop verbatim.** First call: behave
  as if it returned `PGRES_POLLING_WRITING`; loop on `PQcancelSocket` until
  `PGRES_POLLING_OK` / `PGRES_POLLING_FAILED`. `PQcancelSocket` at `:313`,
  `PQcancelStatus` at `:302`, `PQcancelReset` (reuse) at `:337`, `PQcancelFinish`
  (free) at `:353`. [verified-by-code]
- **The new API inherits the original connection's encryption requirements.**
  "if the original connection requires encryption of the connection and/or
  verification of the target host (using `sslmode` or `gssencmode`), then the
  connection for the cancel request is made with these same requirements." The
  legacy API does *not* — a real security gain in PG17. [from-docs]
- **`PQcancelStatus` reuses `ConnStatusType`**: `CONNECTION_ALLOCATED` (initial,
  after Create/Reset), `CONNECTION_OK` (dispatched), `CONNECTION_BAD` (failed),
  plus the async handshake states. Errors via `PQcancelErrorMessage`
  (`fe-cancel.c:325`), which "can consist of multiple lines, and will include a
  trailing newline." [from-docs][verified-by-code]
- **Legacy `PQcancel` is the *only* signal-safe canceller.** `PQgetCancel(PGconn
  *conn)` returns a read-only `PGcancel`; `PQcancel(cancel, errbuf, errbufsize)`
  "can be safely invoked from a signal handler, if the `errbuf` is a local
  variable in the signal handler." It is safe precisely because "The `PGcancel`
  object is read-only… so it can also be invoked from a thread that is separate
  from the one manipulating the `PGconn` object." `PQcancel` at `fe-cancel.c:548`,
  `PQfreeCancel` at `:502`. [verified-by-code] The new `PGcancelConn` path does
  blocking I/O and is **not** signal-safe.
- **`PQrequestCancel` is doubly deprecated and unsafe.** It operates directly on
  the `PGconn` and overwrites its error message: "not safe within
  multiple-thread programs or signal handlers, since it is possible that
  overwriting the `PGconn`'s error message will mess up the operation currently
  in progress." At `fe-cancel.c:752`. [verified-by-code]
- **Cancellation is best-effort with three outcomes.** "Successful dispatch of
  the cancellation is no guarantee that the request will have any effect." If
  effective → the command terminates early with an error result; if it lost the
  race → "there will be no visible result at all." [from-docs]
- **Cleanup is mandatory even on failure.** `PQcancelFinish` must be called on the
  `PGcancelConn` "even on failure"; `PQcancelReset` re-arms one for another
  cancel without reallocating. [from-docs]

## Links into corpus

- Cancel key origin (BackendKeyData in the startup handshake):
  [[knowledge/docs-distilled/protocol-flow.md]],
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- Same poll-loop shape as: [[knowledge/docs-distilled/libpq-connect.md]] (PQconnectPoll).
- Source: [[knowledge/files/src/interfaces/libpq/fe-cancel.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
- Backend cancel handling: [[knowledge/subsystems/libpq-backend.md]] and the
  `process-lifecycle` skill (postmaster routes the cancel to the target backend).
