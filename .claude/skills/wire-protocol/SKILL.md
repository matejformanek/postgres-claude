---
name: wire-protocol
description: PostgreSQL's frontend/backend wire protocol — the byte-level message format between client (libpq or any driver) and backend, plus the backend-side send/receive machinery. Covers `src/backend/libpq/pqcomm.c` (byte-stream framing) + `pqformat.c` (typed message building/parsing) + the message-dispatch loop in `tcop/postgres.c`. Loads when the user asks about protocol version 3.0/3.1, message types (Startup / Query / Bind / Execute / RowDescription / DataRow / CommandComplete / ReadyForQuery / ErrorResponse / etc.), simple vs extended query protocol, protocol negotiation, `pq_beginmessage` / `pq_sendstring` / `pq_endmessage` conventions, adding a new protocol message (has scenario `add-new-protocol-message`), or debugging "backend closed connection unexpectedly" wire-level. Skip when the ask is about libpq's client-side implementation (`src/interfaces/libpq/`), about the replication sub-protocol (walsender's variant), or about authentication protocol details (see `libpq-backend` subsystem).
when_to_load: Add or modify a protocol message; understand simple vs extended query flow; investigate wire-level bugs; touch pq_beginmessage/pq_endmessage lifecycle; work with binary vs text send/recv format.
companion_skills:
  - error-handling
  - process-lifecycle
  - fmgr-and-spi
---

# wire-protocol — the fe/be byte-level protocol

Every PG client-server exchange follows a strict wire protocol: length-prefixed typed messages over a socket. Understanding the message boundary + startup dance + simple-vs-extended dispatch is required for any code that touches network communication or extends the protocol.

Since PG 18, there's also **protocol 3.2** (`PG_PROTOCOL_LATEST` in `src/include/libpq/pqcomm.h:95`). Its main behavioural change is **longer cancel-request keys** (variable-length up to 256 bytes; 4 bytes in 3.0) — see commit `a460251f0a1` "Make cancel request keys longer". libpq exposes `min_protocol_version` / `max_protocol_version` connection options so clients can pin a specific version (commit `285613c60a7`). Version 3.2 does NOT introduce a client-driven ParameterStatus subscription mechanism — GUC change reporting is still gated by the server-side `GUC_REPORT` flag on individual variables (see `ReportChangedGUCOptions` in `src/backend/utils/misc/guc.c`) and is available in all 3.x protocol versions.

## The file map

| File | KB | Role |
|---|---:|---|
| `libpq/pqcomm.c` | 30 | Low-level byte-stream framing. `PqCommMethod` vtable for socket + shared-mem front ends. Length-prefixed reads/writes. |
| `libpq/pqformat.c` | 15 | Typed message building (`pq_beginmessage` / `pq_send*` / `pq_endmessage`) and parsing (`pq_getmsg*`). The extension seam most patches touch. |
| `libpq/be-secure*.c` | — | TLS + GSS setup — sits between socket and pqcomm framing. |
| `libpq/auth*.c` | — | Auth message exchange — the startup phase before the query loop. |
| `tcop/postgres.c` | 146 | The **query loop** — reads next command message, dispatches based on message type, produces response. Sections: simple query, extended query (Parse/Bind/Execute), function call, replication protocol subset. |
| `tcop/backend_startup.c` | 34 | Startup message parsing + protocol negotiation + initial auth-handshake driver. |

The protocol itself is described in `doc/src/sgml/protocol.sgml` — read that for the definitive message list.

## The 3 message-writing patterns

### 1. `pq_beginmessage` / `pq_send*` / `pq_endmessage`

The **standard pattern** for backend → client messages. Batched into a StringInfo, sent atomically.

```c
pq_beginmessage(&buf, 'T');           // RowDescription message
pq_sendint16(&buf, numattrs);
for (i = 0; i < numattrs; i++) {
    pq_sendstring(&buf, attname);
    pq_sendint32(&buf, tableoid);
    /* ... */
}
pq_endmessage(&buf);
```

`pq_beginmessage` sets the message-type byte; `pq_endmessage` writes the length prefix + flushes to the output buffer. Errors between them leak the buffer — see `pgstat_progress_leak` planning doc for exactly this pattern going wrong upstream.

### 2. `pq_beginmessage_reuse` / `pq_endmessage_reuse`

Same shape but reuses the caller's StringInfo across many messages (avoiding repeated palloc/pfree). Used in high-volume paths like DataRow serialization for large query results.

### 3. Direct socket write (rare)

`pq_putbytes` / `pq_flush` — bypasses the message-formatting layer. Used for the initial startup handshake and TLS negotiation.

## Simple vs Extended Query Protocol

### Simple Query ('Q' message)

Client → 'Q' + SQL text. Backend parses + plans + executes + sends RowDescription + DataRows + CommandComplete + ReadyForQuery. Simple, no parameters, no explicit binary format.

### Extended Query (Parse/Bind/Describe/Execute)

The parameterized flow:

1. Client → 'P' (Parse) + prepared-statement name + SQL text + parameter type OIDs. Backend parses + stores as unnamed or named statement.
2. Client → 'B' (Bind) + portal name + statement name + parameter values (binary or text) + result-format codes. Backend plans + creates portal.
3. Client → 'D' (Describe) — optional, requests RowDescription now.
4. Client → 'E' (Execute) + portal name + max-rows. Backend runs; sends DataRows + PortalSuspended (if max hit) or CommandComplete.
5. Client → 'S' (Sync). Backend sends ReadyForQuery. This ends the "extended query pipeline".

The extended protocol is the basis for prepared statements + parameter binding + binary format. Every serious driver uses it.

Between Parse+Bind+Execute the backend is IN a "in the middle of an extended query" state. Errors during this window are handled specially: subsequent messages ignored until Sync arrives. This is the "backend closed connection unexpectedly" investigator's clue.

## Startup phase (before query loop)

1. Client → StartupMessage (no message-type byte for backward compat) + protocol version + database/user/options.
2. Backend picks protocol version; sends AuthenticationRequest.
3. Auth exchange (SCRAM, MD5, TRUST, etc.).
4. Backend sends AuthenticationOk + BackendKeyData (for cancel).
5. Backend sends ParameterStatus for each GUC the client should know (server_version, client_encoding, etc.).
6. Backend sends ReadyForQuery. Now in the query loop.

Which GUCs land in that initial ParameterStatus set is determined by the server-side `GUC_REPORT` flag on individual variables — see the ~15 lines in `src/backend/utils/misc/guc_tables.c` that set `GUC_REPORT` on `client_encoding`, `TimeZone`, `search_path`, `server_version`, etc. Later GUC changes to any `GUC_REPORT`-flagged variable trigger `ReportChangedGUCOptions` which emits a fresh ParameterStatus message to the client. There is no client-side subscription mechanism — the server decides. (Protocol 3.2 does NOT change this; earlier drafts of this skill claimed a `_pq_.report` startup option, which does not exist in the source. T8 triaged 2026-07-13.)

## The pq_beginmessage lifecycle (canonical patch pitfall)

Every `pq_beginmessage` MUST be paired with `pq_endmessage` (or the reuse variant). Missing / duplicate calls between them → leaked StringInfo → memory pressure over time.

This is the class of bug `planning/pgstat_progress_leak/` hunted (byte-identical fix to upstream b20c952ce70): a repeated `initStringInfo` reset inside a wire message being built inside `pgstat_progress_parallel_incr_param()`. See that planning doc + notes.md for the exact pattern.

## Common patch shapes

### Add a new protocol message

Scenario exists: `knowledge/scenarios/add-new-protocol-message.md`. Short:
- Pick a byte for the message type (all-caps letters are backend→client; digits/lowercase for client→backend). Avoid collision with existing types.
- Version-gate via `PG_PROTOCOL_MAJOR / MINOR` in `libpq/pqcomm.h`.
- Client-side: driver support required. libpq changes in `src/interfaces/libpq/`.
- Docs: `doc/src/sgml/protocol.sgml`.

### Add a parameter status report

If a new GUC should be visible in every client's startup ParameterStatus:
- Add to `report_guc_option` in `guc.c`.
- Effect on clients that don't request it: none (they ignore unknown ParameterStatus messages).

### Change binary send/recv format for a type

Every type has `typsend` and `typreceive` funcs in pg_type. Change requires:
- Update the C send/recv fn (typically in `utils/adt/<type>_ops.c`).
- Bump the type's `typreceive` version guard if binary format is versioned.
- Clients using the binary format break. Coordinate on hackers-list.

### Debug "backend closed connection unexpectedly"

- Check server log for the last message BEFORE the crash — often a `LOG: could not send data to client`.
- Look for missing `pq_endmessage` or double `pq_beginmessage`.
- Wireshark filter `tcp.port == 5432` — see the last bytes actually sent.
- Try the query in simple mode (`?options=-c%20standard_conforming_strings=on` or just via psql `-c`) vs extended (via prepared statement) — narrows if issue is in extended-only path.

## Pitfalls

- **StringInfo reset inside a message = bug** — as `pgstat_progress_leak` demonstrated, `initStringInfo` inside `pq_beginmessage`/`pq_endmessage` leaks the outer buffer.
- **Message-type byte case matters** — uppercase = backend→client, lowercase = client→backend, by convention. Digit-prefixed = replication sub-protocol. Don't rebind.
- **Length includes itself but not the type byte** — the 4-byte length prefix counts itself + payload. Off-by-4 bugs are classic.
- **Extended query stays in error state until Sync** — a bug that logs "backend closed connection" during Bind may actually be an unhandled error mid-extended-query. Look for the previous message.
- **Binary format is machine-order** — network byte order for ints, but strings are UTF-8 (server encoding). Getting endianness wrong on ints = subtle data corruption.
- **Cancel is out-of-band** — cancel uses a SEPARATE connection with BackendKeyData. Not a wire message on the query connection.
- **`pq_flush` vs `pq_flush_if_writable`** — flush is blocking; flush_if_writable is non-blocking. Backends normally use non-blocking after each message.
- **TLS renegotiation is disabled** — PG doesn't support mid-connection TLS renegotiation. Don't add features assuming it works.
- **Startup message has NO type byte** — the first message from a client has a length + version + key-value payload, no type prefix. This is why the parser is separate from the query-loop parser.

## Related corpus

- **Idiom**: `error-handling` (`ereport` + protocol ErrorResponse interaction), `plan-cache` (extended-protocol prepared statement caching).
- **Subsystem**: `libpq-backend` (broader — includes auth + TLS + protocol), `tcop` (the query loop).
- **Data structures**: `stringinfo` (message buffer), `pgproc-fields` (per-backend socket handle).
- **Scenarios**: `add-new-protocol-message` (the DDL/patch guide for a new message).
- **Related planning**: `planning/pgstat_progress_leak/` — real-world buffer-lifecycle bug fixed via wire-protocol-adjacent code. Read comparison.md for the byte-identical-to-upstream analysis.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --scenario add-new-protocol-message
python3 scripts/corpus-chain.py --file src/backend/libpq/pqformat.c
python3 scripts/corpus-chain.py --file src/backend/tcop/postgres.c
```

## Boundary

**Use this skill** for the backend-side fe/be protocol byte-formatting layer.

**Don't use** for:
- **libpq client-side** (`src/interfaces/libpq/`) — sibling implementation with its own file map.
- **Walsender's replication sub-protocol** — different message set + different dispatch. See `logical-replication` skill for logical decoding.
- **JDBC / drivers** — external implementations of the same protocol.
- **Authentication protocols** (SCRAM / GSS / LDAP) — see `libpq-backend` subsystem.
