---
source_url: https://www.postgresql.org/docs/current/protocol-overview.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §55.1: Frontend/Backend Protocol Overview

The two-phase wire protocol (startup → normal operation), simple vs extended
query, and the prepared-statement/portal split at the protocol level. Frames the
already-distilled `protocol-flow`, `protocol-message-formats`, and
`protocol-replication` leaf pages.

## Two phases [from-docs]

- **Startup phase** — frontend opens the connection and authenticates; server
  sends status info on success. *"Except for the initial startup-request message,
  this part of the protocol is driven by the server"* (server picks the auth
  method/challenge). [from-docs]
- **Normal operation** — frontend sends queries/commands, backend replies; *"for
  the most part this portion of a session is driven by frontend requests."* The
  backend may still emit unsolicited messages (e.g. `NOTIFY`). [from-docs]
  [verified-by-code, source/src/backend/tcop/postgres.c — `PostgresMain` message
  loop; via knowledge/docs-distilled/protocol-flow.md]

## Message framing [from-docs]

- Every message: **1 byte type identifier**, then **4 bytes length** *(length
  includes itself but not the type byte)*, then the payload. **Exception:** the
  initial startup message has **no type byte**. [from-docs]
- Both ends buffer a whole message before acting; on a detected error a peer skips
  the remaining declared bytes. Never send a partial message. [from-docs]

## Simple vs extended query [from-docs]

- **Simple query**: frontend sends a text query string; backend parses and
  executes it immediately (one `Query` message). [from-docs]
- **Extended query**: split into steps with named/unnamed objects:
  1. **Parse** → a **prepared statement** (result of parse + semantic analysis of
     the text).
  2. **Bind** → a **portal** (the prepared statement with parameter values filled
     in; ready/partially-executed).
  3. **Execute** → run the portal.
  [from-docs]
- Prepared statements are *"optimized for reuse"*; portals are *"optimized for
  single execution then discard"* — for a `SELECT`, an open portal is equivalent
  to an open **cursor**. Both exist **only within a session and are never shared
  across sessions.** [from-docs]
  [verified-by-code, source/src/backend/tcop/pquery.c (portals) +
  utils/cache/plancache.c (prepared statements)]

## Session lifecycle + async messages [from-docs]

- Termination is normally frontend-initiated, but the backend can force it; the
  backend **rolls back any incomplete transaction** before closing. [from-docs]
- The protocol carries unsolicited backend→frontend messages — `NOTIFY`
  delivery, and (per later sections) `NoticeResponse`, `NotificationResponse`,
  `ParameterStatus`. [from-docs]

## Protocol version [from-docs]

- **Current: 3.2** (PG 18+). The 3.2 change enlarged the query-cancel **secret
  key** from a fixed 4 bytes to a variable-length field, redefining
  `BackendKeyData` and the `CancelRequest` payload accordingly. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/protocol-flow.md]] — the concrete message exchanges
  per phase.
- [[knowledge/docs-distilled/protocol-message-formats.md]] — byte-level message
  layouts.
- [[knowledge/docs-distilled/connect-estab.md]] — the postmaster fork that
  precedes the startup phase.
- [[knowledge/docs-distilled/protocol-replication.md]] /
  [[knowledge/docs-distilled/protocol-logical-replication.md]] — the replication
  sub-protocols.

## Gaps / follow-ups

- The async-message catalogue and the full `ReadyForQuery` transaction-status
  indicator are only *referenced* here; their byte detail is in
  protocol-message-formats (already distilled).
