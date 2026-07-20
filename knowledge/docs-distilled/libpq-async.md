---
source_url: https://www.postgresql.org/docs/current/libpq-async.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.4 — Asynchronous Command Processing (the non-blocking send/consume state machine)"
maps_to_skill: wire-protocol
---

# libpq §34.4 — Asynchronous Command Processing

The client-side counterpart of the wire protocol: how a libpq application drives
the frontend/backend message exchange without blocking on `PQexec`. This is the
load-bearing page of the async family — pipeline mode, single-row mode, and the
new cancel API all build on the send/`PQgetResult`-until-NULL loop described here.

## Non-obvious claims

- **`PQexec` is a thin wrapper that throws away results.** "`PQexec` can return
  only one `PGresult` structure. If the submitted command string contains
  multiple SQL commands, all but the last `PGresult` are discarded by `PQexec`."
  The async path (`PQsendQuery` + repeated `PQgetResult`) is the *only* way to
  see every statement's result. [from-docs]
- **The send functions are mutually exclusive per connection.** After
  `PQsendQuery` (or `PQsendQueryParams` / `PQsendPrepare` /
  `PQsendQueryPrepared` / `PQsendDescribePrepared` / `PQsendDescribePortal` /
  `PQsendClosePrepared` / `PQsendClosePortal`), "`PQsendQuery` cannot be called
  again (on the same connection) until `PQgetResult` has returned a null
  pointer." [from-docs] `PQsendQuery` at `source/src/interfaces/libpq/fe-exec.c:1433`,
  `PQsendQueryParams` at `:1509`. [verified-by-code]
- **`PQgetResult` returning NULL is the *only* end-of-command signal.** "must be
  called repeatedly until it returns a null pointer, indicating that the command
  is done. (If called when no command is active, `PQgetResult` will just return a
  null pointer at once.)" Each non-NULL return is one statement's `PGresult` — so
  a multi-statement string yields several. `PQgetResult` at `fe-exec.c:2079`. [verified-by-code]
- **The read loop order is fixed and easy to get wrong:**
  `PQconsumeInput` → check `PQisBusy` → `PQgetResult`. "`PQisBusy` will not itself
  attempt to read data from the server; therefore `PQconsumeInput` must be
  invoked first, or the busy state will never end." `PQisBusy` returns 1 =
  would-block, 0 = safe to call `PQgetResult`. `PQconsumeInput` at `fe-exec.c:2001`,
  `PQisBusy` at `:2048`. [verified-by-code]
- **Overlapped processing is a documented feature, not a side effect.** With a
  multi-command string "the client can be handling the results of one command
  while the server is still working on later queries in the same command
  string." [from-docs]
- **`PQflush` has *three* return values, and `1` is not an error.** `0` = send
  queue emptied, `-1` = error, `1` = "unable to send all data yet" (nonblocking
  only — retry after the socket is writable). `PQflush` at `fe-exec.c:4036`
  (delegates to `pqFlush` at `fe-misc.c:1140`). [verified-by-code]
- **Nonblocking flush must also drain input, or you deadlock.** "If it becomes
  read-ready, call `PQconsumeInput`, then call `PQflush` again… because the
  server can block trying to send us data, e.g., `NOTICE` messages, and won't
  read our data until we read its." This is the same deadlock class the pipeline
  page warns about. [from-docs]
- **`PQsetnonblocking` only changes *send* behavior.** In nonblocking mode
  `PQsendQuery`, `PQputCopyData`, etc. buffer locally instead of blocking;
  `PQgetResult` still blocks unless you gate it behind `PQisBusy`.
  `PQsetnonblocking` at `fe-exec.c:3980`, `PQisnonblocking` at `:4019`. [verified-by-code]
- **In pipeline mode `PQsendQuery` is *disallowed*** (it uses the simple query
  protocol); and `PQgetResult` gains the `PGRES_PIPELINE_SYNC` /
  `PGRES_PIPELINE_ABORTED` result types. See `libpq-pipeline-mode.md`. [from-docs]

## Links into corpus

- Server side of this exact exchange: [[knowledge/docs-distilled/protocol-flow.md]]
  (Simple vs Extended query sub-protocols) and
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- Backend dispatcher that produces these results:
  [[knowledge/subsystems/libpq-backend.md]] and the `wire-protocol` skill.
- Source: [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]],
  [[knowledge/files/src/interfaces/libpq/fe-misc.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-int.h.md]].
- Builds into: `libpq-pipeline-mode.md`, `libpq-single-row-mode.md`,
  `libpq-copy.md`, `libpq-cancel.md`.
