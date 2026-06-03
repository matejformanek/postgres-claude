# pqformat.h

- **Source path:** `source/src/include/libpq/pqformat.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions for formatting and parsing frontend/backend messages" —
StringInfo-based serializers/deserializers used to build and parse the
wire-protocol body bytes (after the 1-byte type + 4-byte length header).

## Public API surface

- Message lifecycle: `pq_beginmessage`, `pq_beginmessage_reuse`,
  `pq_endmessage`, `pq_endmessage_reuse`.
- Senders (StringInfo append, host→network byte order where applicable):
  `pq_sendbytes`, `pq_sendcountedtext`, `pq_sendtext`, `pq_sendstring`
  (with server→client encoding conversion), `pq_send_ascii_string`,
  `pq_sendfloat4`/`8`, `pq_sendbyte`, `pq_sendint8`/`16`/`32`/`64`,
  deprecated polymorphic `pq_sendint(buf, i, b)` (b ∈ {1,2,4}) which
  `elog(ERROR, "unsupported integer size %d", b)` otherwise
  [verified-by-code].
- Pre-enlarged writers (static inline, use `pg_restrict` and an `Assert`
  on remaining `maxlen`): `pq_writeint8`/`16`/`32`/`64`, `pq_writestring`.
  Caller must `enlargeStringInfo()` first; the `pq_send*` wrappers do
  this for you [verified-by-code].
- Typed-value senders: `pq_begintypsend`, `pq_endtypsend` — used by type
  output functions to produce `bytea`-wrapped binary representations.
- Convenience: `pq_puttextmessage`, `pq_putemptymessage`.
- Receivers: `pq_getmsgbyte`, `pq_getmsgint` (1/2/4 bytes), `pq_getmsgint64`,
  `pq_getmsgfloat4`/`8`, `pq_getmsgbytes`, `pq_copymsgbytes`,
  `pq_getmsgtext`, `pq_getmsgstring` (null-terminated, encoding-converted),
  `pq_getmsgrawstring` (no conversion), `pq_getmsgend` (assert nothing
  left).

## Internal landmarks

- All multi-byte writers go through `pg_hton16/32/64`; readers symmetrically
  use `pg_ntoh*` (in `pqformat.c`). Wire format is big-endian network
  byte order [verified-by-code].
- `pq_writestring` converts via `pg_server_to_client` and re-measures
  `slen` if conversion happened — assumes caller pre-allocated enough
  space for the post-conversion length [from-comment].

## Cross-refs

- Related backend: `src/backend/libpq/pqformat.c`.
- Related: `knowledge/files/src/include/libpq/protocol.h.md` (msg type
  codes used as the `msgtype` argument here).

## Potential issues

- **[ISSUE-undocumented-invariant: pq_writestring caller must pre-size for conversion]**
  `pqformat.h:99-124` — the comment warns "The pre-allocated space needs
  to be sufficient for the string after converting to client encoding"
  but enforcement is only the `Assert`. A non-assert build that
  underestimates client-encoding expansion (UTF-8 → multibyte) writes
  past the buffer. The convention "always call `pq_sendstring` if you're
  not certain" is implicit. Severity: maybe.
- **[ISSUE-undocumented-invariant: pq_sendint deprecated path still throws elog]**
  `pqformat.h:170-187` — header marks `pq_sendint` "deprecated; prefer use
  of the functions above" but does not say when it will be removed; new
  callers that pass `b=8` get a runtime `elog(ERROR)` rather than a
  compile-time error. Severity: low.

## Tally

`[verified-by-code]=6 [from-comment]=2`
