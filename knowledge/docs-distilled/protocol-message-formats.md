---
source_url: https://www.postgresql.org/docs/current/protocol-message-formats.html
fetched_at: 2026-06-09T20:48:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Frontend/Backend Protocol Message Formats

Wire-format companion to `protocol-flow`. This is the byte-level reference for
the v3 messages a backend reads/writes; the code that parses/builds them lives
in `src/backend/libpq/pqcomm.c` (transport) and `pqformat.c` (typed get/put).

## The universal framing rule

- Every regular message is **`Byte1` type code + `Int32` length** (length
  *includes itself* but not the type byte), then a type-specific payload. [from-docs]
- The **startup-phase messages are the exception**: `StartupMessage`,
  `SSLRequest`, `GSSENCRequest`, `CancelRequest` have **no leading type byte** —
  they're distinguished by a magic Int32 in place of a normal protocol version.
  Magic codes: SSLRequest `80877103`, GSSENCRequest `80877104`, CancelRequest
  `80877102`. [from-docs]
- Messages are framed so the body end is computable without the length, but the
  length is mandatory and used for validity checking. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/libpq/pqcomm.c.md]]]

## Direction-tagged catalogue (high-yield subset)

- **Frontend→Backend:** `Query` (simple), `Parse`/`Bind`/`Describe`/`Execute`/
  `Sync`/`Close`/`Flush` (extended), `FunctionCall`, `CopyData`/`CopyDone`/
  `CopyFail`, `Terminate`, and the auth replies (`PasswordMessage`,
  `SASLInitialResponse`, `SASLResponse`, `GSSResponse`) which **all share type
  code `'p'`** — the kind is deduced from auth context, not the byte. [from-docs]
- **Backend→Frontend:** `Authentication*` (sub-typed by an Int32: Ok=0,
  CleartextPassword=3, MD5Password=5, GSS=7, SASL=10, SASLContinue=11,
  SASLFinal=12), `BackendKeyData`, `ParameterStatus`, `RowDescription`,
  `DataRow`, `CommandComplete`, `EmptyQueryResponse`, `ReadyForQuery`,
  `ErrorResponse`/`NoticeResponse`, `NotificationResponse`, `ParseComplete`,
  `BindComplete`, `CloseComplete`, `NoData`, `ParameterDescription`,
  `PortalSuspended`, `CopyIn/Out/BothResponse`, `NegotiateProtocolVersion`. [from-docs]

## Non-obvious framing facts worth keeping

- **`ReadyForQuery` carries the transaction status byte**: `'I'` idle, `'T'` in a
  transaction block, `'E'` in a failed transaction block. This is how a client
  knows it must `ROLLBACK` before more work. [from-docs]
- **Format codes are `0`=text, `1`=binary**, settable per-parameter and
  per-result-column in `Bind`; a count of `0` means "all text", `1` means "apply
  this one code to all". [from-docs]
- **`DataRow` column length `-1` means SQL NULL** (vs `0` = empty string); same
  `-1` convention in `FunctionCallResponse`. [from-docs]
- **`CommandComplete` tag encodes the row count**, e.g. `INSERT 0 1`,
  `SELECT 42`, `UPDATE 5` — the leading `0` in INSERT is the historic OID field. [from-docs]
- **`PortalSuspended`** is the backend saying an `Execute` hit its row-count
  limit before the portal was exhausted — resume by sending `Execute` again. [from-docs]
- **`BackendKeyData` secret is now variable (4–256 bytes)** as of protocol v3.2;
  it was always 4 bytes before. A later `CancelRequest` must echo the pid+secret. [from-docs]
- **`CopyData` from the backend always corresponds to a single row**; a frontend
  may split its `CopyData` arbitrarily. [from-docs]
- **`ErrorResponse`/`NoticeResponse` share one format**: a sequence of
  field-tagged strings (severity, SQLSTATE code, message, detail, hint, …)
  terminated by a zero byte. The field-type bytes are listed in the error-fields
  section. [from-docs] [cross: skill `error-handling`]

## Extended-query happy path

`Parse → ParseComplete`, `Bind → BindComplete`, `Execute →`
(`RowDescription` if a SELECT) `DataRow*` `CommandComplete`, then `Sync →
ReadyForQuery`. `Describe` ('S' statement / 'P' portal) yields
`ParameterDescription` + `RowDescription` (or `NoData`). [from-docs]

## Links into corpus
- [[knowledge/docs-distilled/protocol-flow.md]] — the state-machine prose companion.
- [[knowledge/subsystems/libpq-backend.md]] — backend-side protocol subsystem synthesis.
- [[knowledge/files/src/backend/libpq/pqcomm.c.md]] — raw message read/write + buffering.
- [[knowledge/files/src/backend/libpq/pqformat.c.md]] — typed `pq_getmsg*`/`pq_sendint*` builders.
- [[knowledge/files/src/backend/libpq/auth-sasl.c.md]] / [[knowledge/files/src/backend/libpq/auth-scram.c.md]] — the `'p'`-coded SASL exchange.
- [[knowledge/files/src/interfaces/libpq/fe-protocol3.c.md]] — the client-side parser of the same wire format.

## Gaps / follow-ups
- Per-message exact byte layouts (field order within each message) are NOT
  reproduced here — go to the source page or `pqformat.c` for the precise
  `pq_sendint16`/`pq_sendstring` order before hand-coding a message.
- Logical-replication `CopyData` sub-messages have their own format chapter
  (`protocol-logicalrep-message-formats`), not yet distilled.
