# pqcomm.h

- **Source path:** `source/src/include/libpq/pqcomm.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions common to frontends and backends" — shared wire-protocol
constants, the protocol version machinery, the Unix-socket path convention,
and the ALPN string. Despite the name, `pqcomm.c`'s routines are declared
in `libpq.h` [from-comment].

## Public API surface

- Types: `SockAddr`, `AddrInfo`, `ProtocolVersion` (uint32), `PacketLen`
  (uint32), `AuthRequest` (uint32), `CancelRequestPacket { cancelRequestCode,
  backendPID, cancelAuthCode[FLEXIBLE_ARRAY_MEMBER] }`.
- Unix socket macros:
  - `UNIXSOCK_PATH(path, port, sockdir)` — produces `<sockdir>/.s.PGSQL.<port>`.
  - `UNIXSOCK_PATH_BUFLEN` — sizeof sun_path; usually ~100 bytes
    [from-comment].
  - `is_unixsock_path(path)` static-inline — absolute-path or `@` prefix
    means Unix socket.
- Protocol version macros: `PG_PROTOCOL_MAJOR(v)`, `PG_PROTOCOL_MINOR(v)`,
  `PG_PROTOCOL_FULL(v)`, `PG_PROTOCOL(m,n)`.
- **Wire constants — changing breaks all libpq clients and gateways**
  [verified-by-code, from-comment]:
  - `PG_PROTOCOL_EARLIEST (3,0)`, `PG_PROTOCOL_LATEST (3,2)`.
  - `PG_PROTOCOL_RESERVED_31 (3,1)` — skipped because it "would have
    collided with old pgbouncer deployments" [from-comment].
  - `PG_PROTOCOL_GREASE (3,9999)` — intentionally unsupported version for
    protocol-negotiation greasing [from-comment].
  - `CANCEL_REQUEST_CODE (1234,5678)`, `NEGOTIATE_SSL_CODE (1234,5679)`,
    `NEGOTIATE_GSS_CODE (1234,5680)`.
  - `MAX_STARTUP_PACKET_LENGTH 10000` — arbitrary DoS limit
    [from-comment].
  - `PG_ALPN_PROTOCOL "postgresql"` + `PG_ALPN_PROTOCOL_VECTOR` — the
    IANA-registered TLS ALPN identifier, required to defend against
    ALPACA-style cross-protocol attacks [from-comment]. The comment cites
    RFC 7301 and the IANA registry.
- Pulls in `libpq/protocol.h` for the request/response message-type codes.

## Internal landmarks

- `CancelRequestPacket.cancelAuthCode` is now a `FLEXIBLE_ARRAY_MEMBER`
  (since v18 / protocol 3.2); pre-v18 it was a fixed 4 bytes
  [from-comment]. Backwards-compat surface for cancellation handling.

## Cross-refs

- Related backend: `src/backend/libpq/pqcomm.c`.
- Related: `knowledge/files/src/include/libpq/protocol.h.md`,
  `knowledge/files/src/include/libpq/libpq-be.h.md`,
  `knowledge/files/src/include/libpq/libpq.h.md`.
- Frontend: `src/interfaces/libpq/fe-connect.c` consumes these same
  constants.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: ALPN value is wire-load-bearing]**
  `pqcomm.h:189-190` — `PG_ALPN_PROTOCOL "postgresql"` is the
  IANA-registered identifier and must match the client; the header notes
  the IANA registration but doesn't say "do not change" explicitly. A
  patch that "fixed" capitalization would silently break ALPN. Severity:
  likely.
- **[ISSUE-undocumented-invariant: MAX_STARTUP_PACKET_LENGTH is a security knob]**
  `pqcomm.h:148` — value `10000` exists "to prevent simple denial-of-service
  attacks via sending enough data to run the server out of memory" — but
  the header doesn't say which subsystem enforces it (it's the
  `ProcessStartupPacket` path in `backend_startup.c`). Increasing it
  silently weakens that DoS limit. Severity: maybe.
- **[ISSUE-correctness: 1234.567x codes are magic numbers]** `pqcomm.h:122-129`
  — the cancellation/SSL/GSS negotiation codes are historic magic that any
  patch adding a new pre-startup mode (e.g. another negotiation type) must
  not collide with. Worth a "do not change" header note. Severity: maybe.

## Tally

`[verified-by-code]=6 [from-comment]=6 [inferred]=1`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new libpq protocol message](../../../../scenarios/add-new-protocol-message.md)

<!-- scenarios:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
