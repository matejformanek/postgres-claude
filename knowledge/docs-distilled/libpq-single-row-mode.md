---
source_url: https://www.postgresql.org/docs/current/libpq-single-row-mode.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.6 — Retrieving Query Results Row-by-Row (single-row + PG17 chunked mode)"
maps_to_skill: wire-protocol
---

# libpq §34.6 — Retrieving Query Results Row-by-Row

By default libpq buffers a command's *entire* result set into one `PGresult`
before returning it. This mode streams rows (or fixed-size chunks) instead, so a
million-row query doesn't blow up client memory. PG17 added the chunked variant.

## Non-obvious claims

- **The activation window is exactly one call wide.** `PQsetSingleRowMode(conn)`
  / `PQsetChunkedRowsMode(conn, chunkSize)` "can only be called immediately after
  `PQsendQuery` or one of its sibling functions, before any other operation on
  the connection such as `PQconsumeInput` or `PQgetResult`." Wrong timing →
  returns 0, mode unchanged. `PQsetSingleRowMode` at
  `source/src/interfaces/libpq/fe-exec.c:1965`, `PQsetChunkedRowsMode` at `:1982`. [verified-by-code]
- **The mode is per-query and self-resetting.** "This mode selection is effective
  only for the currently executing query" and "the mode reverts to normal after
  completion of the current query." [from-docs]
- **Three result statuses, and a zero-row terminator.** Single-row mode yields
  `PGRES_SINGLE_TUPLE` ("exactly one result row in each" object); chunked mode
  (PG17) yields `PGRES_TUPLES_CHUNK` ("at least one row but not more than the
  specified number of rows per chunk"). "After the last row, or immediately if
  the query returns zero rows, a zero-row object with status `PGRES_TUPLES_OK` is
  returned; this is the signal that no more rows will arrive." Statuses at
  `libpq-fe.h:144` (SINGLE_TUPLE) and `:148` (TUPLES_CHUNK). [verified-by-code]
  You must still call `PQgetResult` until it returns NULL after the terminator. [from-docs]
- **The `PGRES_TUPLES_CHUNK` capability is compile-time detectable.** libpq-fe.h
  carries a feature macro comment: "Indicates presence of `PQsetChunkedRowsMode`,
  `PGRES_TUPLES_CHUNK`" at `libpq-fe.h:51`. [verified-by-code]
- **Errors can arrive *after* rows — the caller owns the rollback.** "in
  single-row or chunked mode, some rows may have already been returned… Hence,
  the application will see some `PGRES_SINGLE_TUPLE` or `PGRES_TUPLES_CHUNK`
  objects followed by a `PGRES_FATAL_ERROR` object." The app "must be designed to
  discard or undo whatever has been done with the previously-processed rows, if
  the query ultimately fails." This is the trap the default full-buffer mode hides. [from-docs]
- **Only the async/extended path supports it** — not `PQexec`. Every partial
  `PGresult` (including the terminal `PGRES_TUPLES_OK`) carries the full row
  description and "should be freed with `PQclear` as usual." [from-docs]
- **In pipeline mode the mode must be re-armed per query.** "single-row or
  chunked mode needs to be activated for each query in the pipeline before
  retrieving results for that query with `PQgetResult`." [from-docs]

## Links into corpus

- Foundation: [[knowledge/docs-distilled/libpq-async.md]] (the send/PQgetResult loop this rides on).
- DataRow wire messages being streamed: [[knowledge/docs-distilled/protocol-message-formats.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
- Combines with: `libpq-pipeline-mode.md`.
