---
source_url: https://www.postgresql.org/docs/current/protocol-changes.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Summary of Changes since Protocol 2.0 (protocol ch. 55.x)

The historical migration record from the wire protocol 2.0 to 3.0 — the version
PostgreSQL has spoken since 7.4. It explains *why the message framing looks the
way it does* in `protocol-message-formats.md`. NOTE: this page is purely the
2.0→3.0 changelog; **minor-version negotiation (3.1/3.2), the
`NegotiateProtocolVersion` message, and the `_pq_.` extension-parameter prefix
live in the protocol-flow / message-flow chapters, not here** (we confirmed the
page carries no 3.1/3.2 content). Pairs with `protocol-overview.md`,
`protocol-flow.md`, and `protocol-message-formats.md`.

## What 3.0 changed vs 2.0 (each is a "why it's shaped this way" note)

- **Startup packet** went from fixed-format to a flexible list of strings; you
  can now set session-default run-time parameters directly in the startup
  packet. [from-docs]
- **Universal length prefix:** every message now carries a length count
  immediately after the message-type byte (the startup packet is the lone
  exception — it has no type byte). `PasswordMessage` gained a type byte. This
  is the framing invariant the message-format parsers rely on. [from-docs]
- **Error/Notice became multi-field.** `ErrorResponse`/`NoticeResponse` (`E`/`N`)
  now carry multiple typed fields for variable verbosity (SQLSTATE, detail, hint,
  position, …); individual fields no longer end in newlines. [from-docs]
- **`ReadyForQuery` (`Z`) gained a transaction-status indicator** (idle / in
  transaction / failed) — the basis of client-side txn-state tracking. [from-docs]
- **One `DataRow` for everything.** The 2.0 `BinaryRow`/`DataRow` split was
  eliminated; a single `DataRow` layout serves all formats, is easier to parse,
  and the binary value representation is **no longer tied to the server's
  internal in-memory representation.** [from-docs]
- **The Extended Query sub-protocol was added wholesale:** `Parse`, `Bind`,
  `Execute`, `Describe`, `Close`, `Flush`, `Sync` and their replies
  (`ParseComplete`, `BindComplete`, `PortalSuspended`, `ParameterDescription`,
  `NoData`, `CloseComplete`). This is the prepared-statement / portal pipeline. [from-docs]
- **COPY was encapsulated** in `CopyData`/`CopyDone` with defined error
  recovery; the magic `\.` terminator is gone, binary COPY is supported, and
  `CopyInResponse`/`CopyOutResponse` carry column count + per-column format.
  [from-docs]
- **`FunctionCall` relaid out** to allow NULL arguments and text-or-binary
  parameters and results. [from-docs]
- **`ParameterStatus` (`S`)** is now sent during startup for every interesting
  GUC and again whenever an active value changes (GUC_REPORT). [from-docs]
- **`RowDescription` (`T`)** gained table-OID + column-number fields and a
  per-column format code. [from-docs]
- **Removed/trimmed:** `CursorResponse` (`P`) is no longer generated;
  `EmptyQueryResponse` (`I`) dropped its trailing empty-string parameter.
  [from-docs]
- **`NotificationResponse` (`A`)** gained the `payload` string field carried
  from the `NOTIFY` sender. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/protocol-overview.md]] — message-flow framing this
  changelog explains.
- [[knowledge/docs-distilled/protocol-flow.md]] — where the modern
  version-negotiation (`NegotiateProtocolVersion`, `_pq_.` params) is actually
  documented.
- [[knowledge/docs-distilled/protocol-message-formats.md]] — the concrete 3.0
  message wire layouts that resulted from these changes.
- [[knowledge/docs-distilled/protocol-message-types.md]] — the `S`/`T`/`Z`/`A`
  type-byte registry referenced above.
- [[knowledge/subsystems/libpq-backend.md]] — backend side that emits these
  messages.

## Open questions

- The 3.1/3.2 minor-version deltas and `_pq_.` negotiation are uncovered by this
  page; confirm whether `protocol-flow.md` already captured them or whether a
  targeted re-mine of the flow chapter's negotiation section is warranted.
