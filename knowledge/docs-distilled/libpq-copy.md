---
source_url: https://www.postgresql.org/docs/current/libpq-copy.html
fetched_at: 2026-07-19T19:56:59Z
anchor_sha: dde9a87d4d02
title: "libpq §34.9 — Functions Associated with the COPY Command (client-side COPY subprotocol)"
maps_to_skill: copy-family
---

# libpq §34.9 — Functions Associated with the COPY Command

The client half of the COPY subprotocol. Once a `COPY` SQL command puts the
connection into copy state, ordinary query functions are locked out until the
data stream ends and `PQgetResult` is called to leave the state.

## Non-obvious claims

- **Copy state is entered by a result status, and locks the connection.**
  `PQexec`/`PQgetResult` returns `PGRES_COPY_IN` (client→server),
  `PGRES_COPY_OUT` (server→client), or `PGRES_COPY_BOTH` (streaming replication
  only). "It is not possible to execute other SQL commands using the same
  connection while the `COPY` operation is in progress." Statuses at
  `source/src/interfaces/libpq/libpq-fe.h:137-143`
  (`PGRES_COPY_OUT`, `PGRES_COPY_IN`, `PGRES_COPY_BOTH`). [verified-by-code]
- **`PGRES_COPY_BOTH` exists solely for the replication protocol** — not
  reachable from a normal SQL `COPY`. [from-docs] Cross-ref
  `protocol-replication.md`.
- **COPY-IN: `PQputCopyData` returns 1 / 0 / -1.** 1 = queued, 0 = buffers full
  (nonblocking only — wait for write-ready and retry), -1 = error. "Buffer-load
  boundaries have no semantic significance when sending" — you can split rows
  across calls arbitrarily. `PQputCopyData` at `fe-exec.c:2712`. [verified-by-code]
- **`PQputCopyEnd(conn, errormsg)` with a non-NULL errormsg forces the COPY to
  fail.** The string becomes the error — but "One should not assume that this
  exact error message will come back from the server… the server might have
  already failed the `COPY` for its own reasons." Returns 1/0/-1 like
  `PQputCopyData`. At `fe-exec.c:2766`. [verified-by-code]
- **COPY-OUT: `PQgetCopyData` returns >0 / 0 / -1 / -2.** >0 = row byte length
  (always >0 on success; "The returned string is always null-terminated"),
  0 = (async only) COPY still in progress, no full row yet, -1 = COPY done,
  -2 = error. At `fe-exec.c:2833`. [verified-by-code]
- **The returned buffer is heap-allocated and must be freed with `PQfreemem`,
  not `free`.** "A non-NULL result buffer should be freed using `PQfreemem` when
  no longer needed." [from-docs]
- **The `async` flag on `PQgetCopyData` selects blocking vs polling.** async=true
  → returns 0 without blocking when no complete row is buffered ("wait for
  read-ready and then call `PQconsumeInput` before calling `PQgetCopyData`
  again"); async=false → blocks until a row or completion. [from-docs]
- **Both directions REQUIRE a trailing `PQgetResult` to leave copy state.** After
  a successful `PQputCopyEnd` (COPY-IN) or a `-1` from `PQgetCopyData` (COPY-OUT),
  "call `PQgetResult` to obtain the final result status of the `COPY` command" —
  this transitions the connection back to normal command state. `PQgetResult` at
  `fe-exec.c:2079`. [verified-by-code]
- **Format helpers on the entry `PGresult`:** `PQnfields` (column count),
  `PQbinaryTuples` (0 text / 1 binary), `PQfformat` (per-column format). [from-docs]

## Links into corpus

- Server-side COPY engine (the other end of this stream): the `copy-family`
  skill and [[knowledge/idioms/tablesync-initial-copy.md]] (logical-replication
  tablesync is built on COPY).
- COPY-BOTH replication path: [[knowledge/docs-distilled/protocol-replication.md]],
  [[knowledge/docs-distilled/logicaldecoding-walsender.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-exec.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
- Foundation: [[knowledge/docs-distilled/libpq-async.md]].
