# libpq-be-fe-helpers.h

- **Source path:** `source/src/include/libpq/libpq-be-fe-helpers.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Header-only library of static-inline helpers that extensions use to drive
libpq from the backend without (a) blocking the postmaster's interrupt
handling and (b) breaking `fd.c`'s FD accounting. Includes
`libpq-be-fe.h` so the `PGresult` macro wrappers compose with these
helpers [from-comment].

## Public API surface (all `static inline`)

- Connection lifecycle:
  - `libpqsrv_connect_start(conninfo)` / `libpqsrv_connect_params_start(...)`
    — start an async connection, having first reserved an external FD via
    `AcquireExternalFD()`.
  - `libpqsrv_connect_complete(conn, wait_event_info)` — drive
    `PQconnectPoll()` against `WaitLatchOrSocket()`, honoring
    `CHECK_FOR_INTERRUPTS()`. Releases the FD on failure.
  - `libpqsrv_connect(conninfo, wait_event_info)`,
    `libpqsrv_connect_params(...)` — convenience wrappers.
  - `libpqsrv_disconnect(conn)` — `PQfinish` + `ReleaseExternalFD`. NULL-safe
    after the documented "no FD reserved" path.
- Query execution:
  - `libpqsrv_exec(conn, query, wait_event_info)` — `PQsendQuery` +
    `libpqsrv_get_result_last`.
  - `libpqsrv_exec_params(...)` — parameterized variant.
  - `libpqsrv_get_result_last`, `libpqsrv_get_result` — interrupt-aware
    `PQgetResult` loops.
- Cancellation: `libpqsrv_cancel(conn, endtime)` — drives `PQcancelPoll()`
  to completion or timeout; returns `NULL` on success, else a non-freeable
  error message [from-comment].
- Notice receiver: `libpqsrv_notice_receiver(arg, res)` — funnels libpq
  NOTICE/WARNING into `ereport(LOG, ...)`. The header temporarily `#undef`s
  the `PGresult` / `PQresultErrorMessage` wrapper macros around this
  function and re-applies them at the bottom [from-comment].

## Internal landmarks

- `libpqsrv_connect_prepare()` may `ereport(ERROR, ...)` if `AcquireExternalFD()`
  fails, with a different `errhint` on Windows (no `ulimit`) [verified-by-code].
- The wrapping macros (`#define PGresult libpqsrv_PGresult`, etc.) come from
  the sibling `libpq-be-fe.h` and are restored after `libpqsrv_notice_receiver`
  so that subsequent extension code sees the wrapped types.

## Cross-refs

- Companion: `knowledge/files/src/include/libpq/libpq-be-fe.h.md`.
- `storage/fd.h` — `AcquireExternalFD` / `ReleaseExternalFD`.
- `storage/latch.h` — `WaitLatchOrSocket`, `MyLatch`.
- Used by `dblink`, `postgres_fdw`, logical replication apply worker.

## Potential issues

- **[ISSUE-stale-todo: connections not put into non-blocking mode]**
  `libpq-be-fe-helpers.h:19-22` — file-top TODO admits that "the connections
  established here are not put into non-blocking mode. That can lead to
  blocking even when only the async libpq functions are used. This should
  be fixed." Genuine known correctness gap — backends using these helpers
  can stall on TCP buffer pressure during long queries. Severity: likely.
- **[ISSUE-leak: documented memory leak in libpqsrv_cancel]**
  `libpq-be-fe-helpers.h:392-394` — comment "this function leaks a string's
  worth of memory when reporting libpq errors. Make sure to call it in a
  transient memory context." The contract is documented but easy to violate
  (caller may be in `TopMemoryContext`); the function does not enforce it.
  Severity: maybe.
- **[ISSUE-correctness: notice receiver assumes wrapper macros are active]**
  `libpq-be-fe-helpers.h:478-506` — the `#undef PGresult` / `#define
  PGresult ...` dance assumes the macros were defined when this header was
  included. A future split that includes this header without the wrappers
  in scope would `#undef` something already undefined (harmless) but the
  re-`#define` would shadow names the consumer did not opt into.
  Severity: maybe.

## Tally

`[verified-by-code]=4 [from-comment]=4`
