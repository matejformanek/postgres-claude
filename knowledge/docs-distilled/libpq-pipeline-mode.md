---
source_url: https://www.postgresql.org/docs/current/libpq-pipeline-mode.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.5 — Pipeline Mode (PG14+): batched extended-protocol queries without per-query round trips"
maps_to_skill: wire-protocol
---

# libpq §34.5 — Pipeline Mode

Added PG14. Lets a client send many extended-protocol commands back-to-back
before reading any result, eliminating per-query network round trips. Built
entirely on the async send/`PQgetResult` loop (see `libpq-async.md`).

## Non-obvious claims

- **Entering pipeline mode sends nothing.** `PQenterPipelineMode` "does not
  actually send anything to the server, it just changes the libpq connection
  state" — it returns 1 on success, 0 if the connection is not idle.
  `PQenterPipelineMode` at `source/src/interfaces/libpq/fe-exec.c:3073`,
  `PQexitPipelineMode` at `:3104`. [verified-by-code]
- **`PQexitPipelineMode` refuses to leave with unconsumed results.** It returns 0
  "if the current statement isn't finished processing, or `PQgetResult` has not
  been called to collect results from all previously sent query." [from-docs]
- **The status enum is three-valued.** `PQpipelineStatus` →
  `PQ_PIPELINE_OFF` / `PQ_PIPELINE_ON` / `PQ_PIPELINE_ABORTED`. Enum at
  `libpq-fe.h:193-195` (note declaration order OFF, ON, ABORTED). [verified-by-code]
  "The aborted flag is cleared when `PQgetResult` returns a result of type
  `PGRES_PIPELINE_SYNC`." [from-docs]
- **Only extended-protocol async functions are legal.** "In pipeline mode, only
  asynchronous operations that utilize the extended query protocol are
  permitted, command strings containing multiple SQL commands are disallowed, and
  so is `COPY`." `PQsendQuery` is disallowed **because it uses the simple query
  protocol**; all synchronous `PQexec*` / `PQprepare` / `PQdescribe*` calls are
  an error. Allowed: `PQsendQueryParams`, `PQsendPrepare`,
  `PQsendQueryPrepared`, `PQsendDescribePrepared`, `PQsendDescribePortal`,
  `PQsendClosePrepared`, `PQsendClosePortal`. [from-docs]
- **Results come back in send order, each terminated by a NULL.** Call
  `PQgetResult` repeatedly per query until NULL, then move to the next query's
  results. A `PGRES_PIPELINE_SYNC` result "is reported exactly once for each
  `PQpipelineSync` or `PQsendPipelineSync` at the corresponding point in the
  pipeline." `PGRES_PIPELINE_SYNC` / `PGRES_PIPELINE_ABORTED` at
  `libpq-fe.h:145-146`. [verified-by-code]
- **First error aborts the whole pipeline until the next sync.**
  `PGRES_PIPELINE_ABORTED` is "emitted in place of a normal query result for the
  first error and all subsequent results until the next `PGRES_PIPELINE_SYNC`."
  The client **must** keep calling `PQgetResult` during error recovery. [from-docs]
- **Commit-confirmation is result-driven, not send-driven.** "The client must
  not assume that work is committed when it *sends* a `COMMIT` — only when the
  corresponding result is received." With multiple explicit transactions in one
  pipeline, transactions committed before the error stay committed; the
  in-progress one aborts; everything after is skipped. [from-docs]
- **Two flush granularities.** `PQpipelineSync` sends a Sync message *and*
  flushes the send buffer; `PQsendPipelineSync` sends Sync *without* flushing
  (caller must `PQflush`). `PQpipelineSync` at `fe-exec.c:3303`,
  `PQsendPipelineSync` at `:3313`. [verified-by-code]
- **`PQsendFlushRequest` flushes server output without a sync point** — i.e.
  without creating an error-recovery boundary. "the request is not itself flushed
  to the server automatically; use `PQflush` if necessary." At `fe-exec.c:3402`. [verified-by-code]
  Server-side results are buffered until a sync or a flush request arrives.
- **Blocking mode risks a documented deadlock.** "The client will block trying to
  send queries to the server, but the server will block trying to send results to
  the client from queries it has already processed" once both the client output
  buffer and the server receive buffer fill. Use non-blocking mode. [from-docs]

## Links into corpus

- Foundation: [[knowledge/docs-distilled/libpq-async.md]] (send / PQgetResult loop).
- Extended protocol on the wire: [[knowledge/docs-distilled/protocol-flow.md]],
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]].
- Interacts with: `libpq-single-row-mode.md` (mode must be re-armed per pipelined query).
