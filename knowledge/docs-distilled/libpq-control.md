---
source_url: https://www.postgresql.org/docs/current/libpq-control.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.11 — Control Functions (client encoding, error verbosity/context enums, PQtrace + trace flags)"
maps_to_skill: wire-protocol
---

# libpq §34.11 — Control Functions

Per-connection knobs that alter how libpq renders errors and mirrors the wire
protocol to a trace file. All settings here are client-side rendering choices —
they never change what the server sends.

## Non-obvious claims

- **`PQclientEncoding` returns an *encoding ID*, not a name.** `-1` on failure;
  convert to a symbolic name (e.g. `EUC_JP`) with `pg_encoding_to_char(id)`.
  `PQsetClientEncoding(conn, name)` returns 0 / -1 and issues a `SET
  client_encoding` under the hood, so it also updates the cached
  `PQparameterStatus("client_encoding")`. [from-docs]
- **`PGVerbosity` is a 4-level ladder** (`source/src/interfaces/libpq/libpq-fe.h:162-165`):
  `PQERRORS_TERSE` (single line: severity, primary text, position only),
  `PQERRORS_DEFAULT` (adds detail/hint/context, may be multi-line),
  `PQERRORS_VERBOSE` (all fields), `PQERRORS_SQLSTATE` (only severity + SQLSTATE
  code). `PQsetErrorVerbosity` returns the previous setting. [verified-by-code][from-docs]
- **Verbosity is captured at PGresult creation, not at read.** "Changing the
  verbosity setting does not affect the messages available from already-existing
  `PGresult` objects, only subsequently-created ones." Same
  copy-at-creation model as the notice hooks. [from-docs]
- **`PGContextVisibility` controls the CONTEXT field independently**
  (`libpq-fe.h:170-172`): `PQSHOW_CONTEXT_NEVER`, `PQSHOW_CONTEXT_ERRORS`
  (default — errors only, not notices/warnings), `PQSHOW_CONTEXT_ALWAYS`. But
  verbosity wins: "if the verbosity setting is `TERSE` or `SQLSTATE`, `CONTEXT`
  fields are omitted regardless of the context display mode." [verified-by-code][from-docs]
- **`PQtrace(conn, FILE*)` dumps both directions to a stream.** Line format is
  tab-separated metadata then space-separated contents:
  `timestamp  direction  length  type  contents`, with `F` = frontend→server,
  `B` = backend→client. `PQuntrace` turns it off. [from-docs]
- **`PQsetTraceFlags` must be called *after* `PQtrace`**, and takes
  `PQTRACE_SUPPRESS_TIMESTAMPS` (`1<<0`,
  `source/src/interfaces/libpq/libpq-fe.h:495`) to drop the leading timestamp and
  `PQTRACE_REGRESS_MODE` (`1<<1`, `:497`) to redact volatile fields like object
  OIDs — that second flag exists specifically so trace output can be diffed in
  regression tests. [verified-by-code][from-docs]
- **The trace machinery lives in its own file.** The formatter is
  `fe-trace.c`, kept separate from `fe-exec.c` — meaning tracing is a pure
  observer bolted onto the protocol reader/writer, not woven into it. [inferred]

## Links into corpus

- Notice hooks share the same "captured at creation" model but are a separate
  page: [[knowledge/docs-distilled/libpq-notice-processing.md]].
- Error fields (severity/SQLSTATE/CONTEXT) these knobs select from:
  [[knowledge/docs-distilled/protocol-error-fields.md]],
  [[knowledge/docs-distilled/error-message-reporting.md]].
- Backend side that produces these fields: the `error-handling` skill (ereport /
  errdetail / errcontext).
- Trace direction markers map to the wire messages in
  [[knowledge/docs-distilled/protocol-message-types.md]].
- Source: [[knowledge/files/src/interfaces/libpq/fe-trace.c.md]],
  [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
