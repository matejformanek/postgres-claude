---
source_url: https://www.postgresql.org/docs/current/protocol-flow.html
parent_chapter: https://www.postgresql.org/docs/current/protocol.html
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §54.2: Frontend/Backend Protocol — Message Flow

The wire-protocol message flow as the **backend** sees it — the spec the
`postgres.c` main loop and `pqcomm`/`libpq-backend` implement. Distilled because
the protocol shape (simple vs extended, Sync semantics, the ReadyForQuery status
byte) is the thing that makes backend message-loop code legible.

## Startup / authentication handshake

- Frontend → **StartupMessage** (user, database, protocol version). Backend →
  an `Authentication*` request (Ok / CleartextPassword / MD5Password / GSS /
  **SASL** / …). [from-docs]
- On success the backend sends **`BackendKeyData`** — "secret-key data that the
  frontend must save if it wants to be able to issue cancel requests later" — then
  zero+ **`ParameterStatus`** (initial GUC values like `server_version`,
  `client_encoding`), then **`ReadyForQuery`**: "Start-up is completed. The
  frontend can now issue commands." [from-docs] [via knowledge/subsystems/libpq-backend.md]

## Simple Query protocol

- One **Query** message carries a text string that **may contain multiple
  statements separated by semicolons**. Response per result set: `RowDescription`
  → 0+ `DataRow` → `CommandComplete`, ending the whole cycle with `ReadyForQuery`.
  [from-docs]
- **Multi-statement Query runs as one implicit transaction:** "those statements are
  executed as a single transaction, unless explicit transaction control commands
  are included to force a different behavior." A failure rolls back the lot (unless
  an earlier explicit COMMIT already committed). [from-docs — exact]

## Extended Query protocol (the part worth knowing)

- Decomposes the cycle into separately-issued messages: **Parse → Bind → (Describe)
  → Execute → … → Sync**. "The simple Query message is approximately equivalent to
  the series Parse, Bind, portal Describe, Execute, Close, Sync, using the unnamed
  prepared statement and portal objects and no parameters." [from-docs — exact]
  - **Parse** compiles a query string into a (named or unnamed) **prepared
    statement** → `ParseComplete`. **One statement only**: "The query string
    contained in a Parse message cannot include more than one SQL statement; else a
    syntax error is reported." [from-docs — exact]
  - **Bind** binds parameter values + result formats to make a **portal** →
    `BindComplete`. (Named statements/portals persist across cycles; unnamed ones
    are replaced by the next Parse/Bind.)
  - **Describe** (optional) returns `ParameterDescription` and/or `RowDescription`.
  - **Execute** runs the portal, returning the same `DataRow…CommandComplete` as a
    simple query (no `RowDescription` — you got it from Describe).
- **Sync is the resynchronization point.** "At completion of each series of
  extended-query messages, the frontend should issue a Sync message. This …
  causes the backend to close the current transaction if it's not inside a
  `BEGIN`/`COMMIT` … Then a ReadyForQuery response is issued. … When an error is
  detected while processing any extended-query message, the backend issues
  ErrorResponse, then reads and discards messages until a Sync is reached, then
  issues ReadyForQuery and returns to normal message processing." [from-docs — exact]
  - **Sync does NOT close a `BEGIN` block** — detectable via the ReadyForQuery
    transaction-status byte. [from-docs]

## ReadyForQuery transaction-status byte

- Every `ReadyForQuery` carries a one-byte status: **`I`** = idle (no transaction),
  **`T`** = in a transaction block, **`E`** = in a *failed* transaction block
  (commands rejected until rollback). This byte is how a client (and `psql`) tracks
  transaction state without parsing SQL. [from-docs/inferred]

## COPY sub-protocol & pipelining

- **COPY** flips the connection into a sub-mode: `CopyInResponse` (FROM STDIN;
  frontend sends `CopyData…` then `CopyDone`/`CopyFail`), `CopyOutResponse` (TO
  STDOUT; backend streams `CopyData…CopyDone`), and **copy-both** for
  **replication** (both sides stream until a `CopyDone`). [from-docs]
- **Pipelining** rides the extended protocol: send many cycles without waiting.
  Because the backend "will skip command messages until it finds Sync," a failed
  command auto-skips the rest of its pipeline up to the next Sync — no client-side
  BEGIN/COMMIT juggling needed. [from-docs]

## Links into corpus

- [[knowledge/subsystems/libpq-backend.md]] — the backend side of pqcomm /
  the message reader-writer implementing this flow.
- [[knowledge/subsystems/tcop.md]] — `PostgresMain` / `exec_simple_query` /
  `exec_parse_message` etc. that dispatch on these message types.
- [[knowledge/docs-distilled/runtime-config-replication.md]] — the copy-both
  replication mode this protocol underpins.
- [[knowledge/subsystems/replication.md]] — walsender consumes copy-both.

## Gaps / follow-ups

- The exact `ReadyForQuery` status byte values (`I`/`T`/`E`) are stated from
  protocol knowledge; the canonical enum is `TransactionStatusType` in the backend
  — a one-line source verify would upgrade that bullet from [inferred] to
  [verified-by-code]. SASL detail lives in §54.3 (sasl-authentication), not mined
  here. Message *formats* (§54.7) are reference, not distilled.
