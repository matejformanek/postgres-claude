# protocol.h

- **Source path:** `source/src/include/libpq/protocol.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions of the request/response codes for the wire protocol." A
header of nothing but `#define`s that names every single-byte message-type
discriminator and every `AUTH_REQ_*` numeric subcode used by the v3
frontend/backend protocol. Pulled into both backend and clients
[from-comment].

## Public API surface — all wire-protocol constants

**Every byte value below is on-the-wire — changing any of them breaks
every libpq client, every gateway (pgbouncer, pgpool), every non-PG
driver (JDBC, npgsql, asyncpg, psycopg). The header has no "do not
change" warning** [verified-by-code].

- Frontend → backend (single ASCII byte):
  - `PqMsg_Bind 'B'`, `PqMsg_Close 'C'`, `PqMsg_Describe 'D'`,
    `PqMsg_Execute 'E'`, `PqMsg_FunctionCall 'F'`, `PqMsg_Flush 'H'`,
    `PqMsg_Parse 'P'`, `PqMsg_Query 'Q'`, `PqMsg_Sync 'S'`,
    `PqMsg_Terminate 'X'`, `PqMsg_CopyFail 'f'`.
  - Auth replies all use `'p'`: `PqMsg_GSSResponse`,
    `PqMsg_PasswordMessage`, `PqMsg_SASLInitialResponse`,
    `PqMsg_SASLResponse` — same byte, disambiguated only by exchange
    state.
- Backend → frontend:
  - `PqMsg_ParseComplete '1'`, `BindComplete '2'`, `CloseComplete '3'`,
    `NotificationResponse 'A'`, `CommandComplete 'C'`, `DataRow 'D'`,
    `ErrorResponse 'E'`, `CopyInResponse 'G'`, `CopyOutResponse 'H'`,
    `EmptyQueryResponse 'I'`, `BackendKeyData 'K'`, `NoticeResponse 'N'`,
    `AuthenticationRequest 'R'`, `ParameterStatus 'S'`,
    `RowDescription 'T'`, `FunctionCallResponse 'V'`,
    `CopyBothResponse 'W'`, `ReadyForQuery 'Z'`, `NoData 'n'`,
    `PortalSuspended 's'`, `ParameterDescription 't'`,
    `NegotiateProtocolVersion 'v'`.
- Both directions: `PqMsg_CopyDone 'c'`, `PqMsg_CopyData 'd'`.
- Parallel worker → leader: `PqMsg_Progress 'P'` (collides with frontend
  `Parse 'P'`, OK because direction disambiguates).
- Replication / backup codes (carried inside `CopyData` payloads):
  `PqReplMsg_Keepalive 'k'`, `_PrimaryStatusUpdate 's'`, `_WALData 'w'`,
  `_HotStandbyFeedback 'h'`, `_PrimaryStatusRequest 'p'`,
  `_StandbyStatusUpdate 'r'`; `PqBackupMsg_Manifest 'm'`,
  `_NewArchive 'n'`, `_ProgressReport 'p'`.
- AuthRequest subcodes (sent inside `AuthenticationRequest 'R'`):
  `AUTH_REQ_OK 0`, `AUTH_REQ_KRB4 1` (retired), `AUTH_REQ_KRB5 2`
  (retired), `AUTH_REQ_PASSWORD 3`, `AUTH_REQ_CRYPT 4` (retired),
  `AUTH_REQ_MD5 5`, `6` reserved (was SCM creds), `AUTH_REQ_GSS 7`,
  `AUTH_REQ_GSS_CONT 8`, `AUTH_REQ_SSPI 9`, `AUTH_REQ_SASL 10`,
  `AUTH_REQ_SASL_CONT 11`, `AUTH_REQ_SASL_FIN 12`, `AUTH_REQ_MAX`
  (= last value) [from-comment].

## Cross-refs

- Related: `knowledge/files/src/include/libpq/pqcomm.h.md` (protocol
  version, ALPN, cancel/SSL/GSS negotiation codes),
  `knowledge/files/src/include/libpq/pqformat.h.md` (the `msgtype`
  argument to `pq_beginmessage`),
  `knowledge/files/src/include/libpq/sasl.h.md` (`AUTH_REQ_SASL*`
  subcodes are the wire face of the SASL exchange).
- Frontend: `src/interfaces/libpq/fe-protocol3.c` consumes the same
  constants.

## Potential issues

- **[ISSUE-undocumented-invariant: every byte is wire-load-bearing]**
  `protocol.h:1-111` — file-top comment says only "Definitions of the
  request/response codes for the wire protocol." It does not say "do
  not renumber, do not change byte values, do not reuse retired codes
  without a protocol-major bump." A careless renumbering would compile
  cleanly and silently break every client. Phase D hardening candidate.
  Severity: likely.
- **[ISSUE-undocumented-invariant: 'p' is overloaded across four FE msgs]**
  `protocol.h:30-33` — `PqMsg_GSSResponse`, `PqMsg_PasswordMessage`,
  `PqMsg_SASLInitialResponse`, `PqMsg_SASLResponse` all share `'p'`.
  Disambiguation depends entirely on which `AUTH_REQ_*` the server
  previously emitted, so a state-machine bug that loses track of auth
  state can confuse one for another. The header lists them adjacently
  but doesn't spell out the contract. Severity: maybe.
- **[ISSUE-undocumented-invariant: retired codes still occupy slots]**
  `protocol.h:97-102` — codes 1, 2, 4, 6 are retired but their numbers
  cannot be reassigned (an old client speaking proto 3.0 may still
  attempt them). Worth a "reserved, do not reassign" comment. Severity:
  maybe.

## Tally

`[verified-by-code]=4 [from-comment]=2 [inferred]=2`
