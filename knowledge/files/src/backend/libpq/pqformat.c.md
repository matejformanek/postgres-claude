---
path: src/backend/libpq/pqformat.c
anchor_sha: 4b0bf0788b0
loc: 640
depth: medium
---

# pqformat.c

- **Source path:** `source/src/backend/libpq/pqformat.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 640

## Purpose

Message-encoding/decoding helpers above `pqcomm.c`. The send side builds an
expansible `StringInfo` (with the message-type byte stashed in `buf->cursor`)
and ships it in one `pq_putmessage` call — guaranteeing that an `ereport(ERROR)`
mid-construction never leaves a half-message on the wire. The receive side
parses a pre-loaded `StringInfo` byte-by-byte, doing endian fix-up and
encoding conversion. Same routines back the binary `typsend`/`typreceive`
flow (no socket I/O — just StringInfo formatting). [from-comment, pqformat.c:1-30]

## Public API surface

### Outgoing message assembly
| Line | Symbol | Notes |
|---|---|---|
| 87 | `pq_beginmessage(buf, msgtype)` | `initStringInfo` + stash msgtype in `buf->cursor` |
| 108 | `pq_beginmessage_reuse(buf, msgtype)` | Same but `resetStringInfo` — buffer kept across calls; caller owns context lifetime |
| 125 | `pq_sendbytes(buf, data, len)` | Raw append (uses NT variant) |
| 141 | `pq_sendcountedtext(buf, str, slen)` | 4-byte count + encoded payload, no NUL |
| 171 | `pq_sendtext(buf, str, slen)` | Encoded, no count, no NUL — for binary typsend |
| 194 | `pq_sendstring(buf, str)` | Encoded + trailing NUL |
| 226 | `pq_send_ascii_string(buf, str)` | NUL-terminated, NO conversion; high-bit chars → `?` |
| 251 / 275 | `pq_sendfloat4/8` | Type-pun via union, endian-swap as int4/int8 |
| 295 | `pq_endmessage(buf)` | `pq_putmessage(cursor, data, len)` then `pfree(buf->data)` |
| 313 | `pq_endmessage_reuse(buf)` | Send but do NOT free; pair with `pq_beginmessage_reuse` |

### typsend/bytea construction
| Line | Symbol | Notes |
|---|---|---|
| 324 | `pq_begintypsend(buf)` | `initStringInfo` + reserve 4 zero bytes for varlena header |
| 344 | `pq_endtypsend(buf)` | `SET_VARSIZE(buf->data, buf->len)`; returns bytea* — does NOT free |

### Special-case output
| Line | Symbol | Notes |
|---|---|---|
| 365 | `pq_puttextmessage(msgtype, str)` | One-shot encoded NUL-term message |
| 386 | `pq_putemptymessage(msgtype)` | Body-less message |

### Incoming message parsing
| Line | Symbol | Notes |
|---|---|---|
| 397 | `pq_getmsgbyte(msg)` | 1 byte; ereport on EOF |
| 413 | `pq_getmsgint(msg, b)` | b ∈ {1,2,4}, returns unsigned, ntoh |
| 451 | `pq_getmsgint64(msg)` | 8 bytes, ntoh64 |
| 467 / 486 | `pq_getmsgfloat4/8` | Bit-cast via union from int |
| 506 | `pq_getmsgbytes(msg, len)` | Pointer into buffer — caller copies if needed |
| 526 | `pq_copymsgbytes(msg, *buf, len)` | Same but copies to caller |
| 544 | `pq_getmsgtext(msg, raw, *nbytes)` | Counted text, palloc'd, encoded |
| 577 | `pq_getmsgstring(msg)` | NUL-term encoded; may return interior pointer |
| 606 | `pq_getmsgrawstring(msg)` | NUL-term, NO conversion, interior pointer |
| 633 | `pq_getmsgend(msg)` | Assert cursor == len, ereport otherwise |

## Internal landmarks

- The "stash msgtype in `buf->cursor`" trick (pq_beginmessage / pq_endmessage)
  saves a byte of allocation but is a foot-gun: any `pq_sendXXX` that
  touched `cursor` would silently corrupt the type. The comment is
  defensive about this. [from-comment, pqformat.c:92-96]
- `pq_begintypsend` writes four `\0` bytes at the start so `pq_endtypsend`
  can `SET_VARSIZE` in place — the returned `bytea*` IS the StringInfo's
  `data` pointer. Caller must NOT pfree the StringInfo. [from-comment, pqformat.c:336-342]
- All read-side bounds checks ereport with `ERRCODE_PROTOCOL_VIOLATION` —
  i.e. unrecoverable; the connection is killed by the outer loop.
  [verified-by-code, pqformat.c:400-403,511-514,529-532,591-594,620-623,636-639]
- `pq_getmsgstring` exploits StringInfo's documented trailing NUL to
  `strlen` safely, then verifies the NUL is *inside* the message via
  `cursor + slen >= len`. The `>=` (not `>`) is correct because slen
  excludes the NUL. [from-comment, pqformat.c:586-589] [verified-by-code, pqformat.c:590-595]

## Invariants & gotchas

- **All outgoing messages are constructed in full, then shipped in one
  `pq_putmessage`.** This is the *whole reason* pqformat exists — see
  `pqcomm.c` top-of-file. Don't add a "stream a chunk now" API without
  understanding the ereport-mid-message recovery story.
- **`pq_getmsgint` is unsigned.** A negative on-wire value will overflow
  silently into a huge `unsigned int`. Callers that expect signed (e.g.
  message-length fields) must cast. [from-comment, pqformat.c:410]
- **`pq_getmsgbytes` / `pq_getmsgstring` / `pq_getmsgrawstring` return
  pointers INTO the message buffer.** If the caller stashes them past
  message lifetime, dangling pointer. [from-comment, pqformat.c:501-504,572-575,602-604]
- **Encoding conversion can re-allocate.** `pg_server_to_client` /
  `pg_client_to_server` return the input pointer unchanged when no
  conversion is needed; an `if (p != str)` check distinguishes. Forget the
  check and you'll leak (or double-free) the converted buffer. [verified-by-code, pqformat.c:146-158, 200-208, 371-377]
- **`pq_send_ascii_string` is the last-resort error path.** It replaces
  any high-bit char with `?` — used only when the encoding conversion
  itself is broken. Don't reach for it to "skip conversion for speed";
  it's intentional information loss. [from-comment, pqformat.c:212-225]

## Cross-refs

- Header: `source/src/include/libpq/pqformat.h`
- Layer below: `source/src/backend/libpq/pqcomm.c` (`pq_putmessage`,
  `pq_getmessage`)
- Layer above: every executor `printtup`, `auth.c`, `walsender.c`,
  `copy.c` (binary mode), every type's `typsend`/`typreceive`
- StringInfo primitive: `source/src/common/stringinfo.c`

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-correctness: pq_getmsgint signed-overflow trap]**
  `pqformat.c:413-441` — `pq_getmsgint(msg, 4)` returns `unsigned int`. A
  hostile message-length of `0xFFFFFFFF` becomes 4 GB and likely passes
  the `<= maxlen` check only if `maxlen` is also unsigned. Cross-check
  every length-prefix consumer in COPY / replication / extension protocol.
  severity: maybe
- **[ISSUE-correctness: pq_getmsgbytes negative-datalen check]**
  `pqformat.c:511-514` does check `datalen < 0`, but the same call from
  `pq_getmsgtext` (pqformat.c:550) and `pq_copymsgbytes` (pqformat.c:529)
  rely on int arithmetic — a caller passing `INT32_MIN` would underflow
  in `msg->len - msg->cursor`. Likely benign because StringInfo lengths
  are non-negative ints, but anyone synthesizing a StringInfo from
  untrusted shm-mq input should be careful. severity: maybe
- **[ISSUE-undocumented-invariant: msgtype stashed in cursor field]**
  pqformat.c:97 — `buf->cursor` is repurposed pre-send, then set to
  `0` by parsing helpers. If any future sendXXX routine touched `cursor`
  (none currently does), the message type would be silently corrupted.
  Worth an explicit `Assert(buf->cursor == msgtype)` in pq_endmessage.
  severity: nit
- **[ISSUE-stale-todo: pq_putmessage_v2 vestige in pqcomm.c]** Not in
  this file but related: pqformat.c has no v2 path, while pqcomm.c keeps
  `pq_putmessage_v2`. If pqformat ever grows a v2 caller this asymmetry
  bites. severity: nit

## Tally

`[verified-by-code]=12 [from-comment]=11 [inferred]=0`
