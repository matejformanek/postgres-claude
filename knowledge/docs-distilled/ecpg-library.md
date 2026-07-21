---
source_url: https://www.postgresql.org/docs/current/ecpg-library.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Library Functions (§36 leaf): ECPGdebug / ECPGget_PGconn / ECPGtransactionStatus / ECPGstatus — the libecpg escape hatches into libpq"
maps_to_skill: wire-protocol
---

# ECPG — Library Functions (the libecpg public escape hatches)

The small set of `libecpg` functions an application may call *directly*
(everything else is code-generated `ECPGdo`/`ECPGconnect`/… calls). These are
the seams where an ECPG program can drop down to raw libpq or turn on
diagnostics. All are declared in `source/src/interfaces/ecpg/include/ecpglib.h`.

## Non-obvious claims

- **`ECPGdebug(int on, FILE *stream)` logs the *substituted* SQL + server
  results.** Definition `source/src/interfaces/ecpg/ecpglib/misc.c:204`
  (`ECPGdebug(int n, FILE *dbgs)` — note the header/docs call the first arg
  `on` but the code names it `n`). When enabled it dumps each statement with
  input variables already substituted plus what the server returned — the
  primary way to see what SQL ECPG actually generated. [verified-by-code]

- **`ECPGdebug` can *crash* the app on Windows across build-flag mismatches.**
  The docs warn: if `libecpg` and the application are built with different
  runtime flags (multithreaded/single-threaded, release/debug, static/dynamic),
  the `FILE *` passed in has a different internal representation on each side
  and the call crashes. This is the same DLL-heap/CRT-boundary hazard that
  drives `PQfreemem`/`PGTYPESchar_free` (see `ecpg-misc`/`ecpg-pgtypes`).
  [from-docs]

- **`ECPGget_PGconn(const char *connection_name)` hands you the raw libpq
  `PGconn`.** Returns the underlying `PGconn *` for the named connection, or
  the *current* connection when passed `NULL`; `NULL` return means no such
  connection (`source/src/interfaces/ecpg/ecpglib/connect.c:737`, decl
  `ecpglib.h:40`). The docs are explicit that "it is a bad idea to manipulate
  database connection handles made from ecpg directly with libpq routines" —
  it's meant for read-only introspection (e.g. `PQparameterStatus`), not for
  issuing queries behind ECPG's back. [verified-by-code][from-docs]

- **`ECPGtransactionStatus` returns libpq's *own* enum.** Its return type is
  `PGTransactionStatusType` (decl `ecpglib.h:41`) — the identical five-state
  enum (`PQTRANS_IDLE`/`ACTIVE`/`INTRANS`/`INERROR`/`UNKNOWN`) documented for
  libpq's `PQtransactionStatus`. ECPG doesn't invent its own transaction-state
  vocabulary; it forwards libpq's. See
  `knowledge/docs-distilled/libpq-status.md`. [verified-by-code]

- **`ECPGstatus(int lineno, const char *connection_name)` is a boolean
  liveness probe.** Returns `true` if a connection to the database is currently
  open, `false` otherwise (`source/src/interfaces/ecpg/ecpglib/misc.c:127`,
  decl `ecpglib.h:25`); `NULL` name means the single/current connection. The
  `lineno` arg exists only so a failure can be reported against the source
  line, matching every other `libecpg` entry point. [verified-by-code]

- **The whole public surface is `bool`/pointer-returning and line-numbered.**
  The other generated entry points in the same header — `ECPGconnect`,
  `ECPGdisconnect`, `ECPGsetcommit`, `ECPGsetconn`, `ECPGtrans`, `ECPGprepare`,
  `ECPGdeallocate[_all]` (`ecpglib.h:24-38`) — all take a leading `int lineno`
  and return `bool` success. `ECPGget_sqlca()` (`misc.c:108`) is how the
  runtime fetches the thread-local `sqlca` those functions populate on failure.
  [verified-by-code]

## Links into corpus

- The `sqlca` these functions populate: `knowledge/docs-distilled/ecpg-errors.md`.
- Underlying libpq accessors an app reaches via `ECPGget_PGconn`:
  `knowledge/docs-distilled/libpq-status.md`,
  `knowledge/docs-distilled/libpq-misc.md`.
- The generated `ECPGdo` runtime these sit beside:
  `knowledge/docs-distilled/ecpg-develop.md`.
- Skill: `wire-protocol`.
