---
path: src/interfaces/libpq/fe-misc.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1443
depth: deep
---

# fe-misc.c

- **Source path:** `source/src/interfaces/libpq/fe-misc.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 1443
- **Companion files:** `libpq-int.h` (PGconn buffer fields: inBuffer, inStart, inCursor, inEnd, inBufSize, outBuffer, outCount, outBufSize, outMsgStart, outMsgEnd), `fe-secure.c` (`pqsecure_read`/`pqsecure_write` — the TLS-aware byte movers this file wraps), `fe-protocol3.c` (the consumer of every `pqGet*`)

## Purpose

The byte-level toolkit. Everything above protocol-3 calls these. Three concerns:

1. **Message-build primitives** for the outgoing direction: `pqPutc`, `pqPuts`, `pqPutnchar`, `pqPutInt`, `pqPutMsgStart`/`pqPutMsgEnd` for framing.
2. **Message-parse primitives** for the incoming direction: `pqGetc`, `pqGets`, `pqGetnchar`, `pqSkipnchar`, `pqGetInt`. These return EOF (non-zero) if the requested bytes aren't yet in the buffer — the caller (typically `pqParseInput3`) rewinds and waits for more I/O.
3. **Buffer & socket I/O**: `pqCheckInBufferSpace` / `pqCheckOutBufferSpace`, `pqReadData`, `pqSendSome`, `pqFlush`, `pqWait`, `pqWaitTimed`, `pqReadReady`, `pqWriteReady`, `PQsocketPoll`.

Plus version helpers (`PQlibVersion`, `PQgetCurrentTimeUSec`) and multibyte length helpers exposed for apps (`PQmblen`, `PQmblenBounded`, `PQdsplen`).

## Public API surface

| Function | Line | One-liner |
|---|---|---|
| `PQlibVersion` | 63 | Returns the libpq build-time version number (PG_VERSION_NUM). |
| `PQsocketPoll` | 1141 | Exposed `poll(2)`/`select(2)` wrapper with timeout. |
| `PQgetCurrentTimeUSec` | 1235 | Monotonic-ish timestamp in microseconds. |
| `PQmblen` | 1255 | Length of one multibyte char in given encoding. |
| `PQmblenBounded` | 1266 | Same but bounded to a passed max length. |
| `PQdsplen` | 1276 | Display-width of one multibyte char (for tabular layout). |

Internal (named `pq*`, not in the PQ\* public surface; linked from libpq.so for sister files):

`pqGetc`, `pqPutc`, `pqGets`, `pqGets_append`, `pqPuts`, `pqGetnchar`, `pqSkipnchar`, `pqPutnchar`, `pqGetInt`, `pqPutInt`, `pqCheckOutBufferSpace`, `pqCheckInBufferSpace`, `pqParseDone`, `pqPutMsgStart`, `pqPutMsgEnd`, `pqReadData`, `pqFlush`, `pqWait`, `pqWaitTimed`, `pqReadReady`, `pqWriteReady`, plus statics `pqGets_internal`, `pqPutMsgBytes`, `pqSendSome`, `pqSocketCheck`.

## Internal landmarks

### Buffer geometry

`PGconn` maintains two ring-like buffers:

- **Input buffer** (`inBuffer`, size `inBufSize`):
  - `inStart` — start of the current partially-consumed message (or oldest unparsed byte).
  - `inCursor` — where the parser is right now (advanced by `pqGet*`).
  - `inEnd` — first byte after data read from socket but not yet consumed.
  - Invariant: `0 ≤ inStart ≤ inCursor ≤ inEnd ≤ inBufSize`.
- **Output buffer** (`outBuffer`, size `outBufSize`):
  - `outCount` — number of bytes pending send to socket.
  - `outMsgStart` — offset of the in-progress message's length-word (or -1 if none).
  - `outMsgEnd` — first byte after the in-progress message's data.

`pqCheckInBufferSpace` (351) and `pqCheckOutBufferSpace` (287) both do: if too small, try to left-justify what's already there (memmove inStart..inEnd to 0), and if still short, double size then increment by 8 KiB. Integer overflow on `newsize *= 2` is guarded explicitly. [verified-by-code, fe-misc.c:286-440]

### Message framing on the way out

```
pqPutMsgStart(msg_type, conn)         → reserves a length word at outBuffer + outMsgStart
pqPutInt / pqPutc / pqPutnchar ...    → append message body via pqPutMsgBytes
pqPutMsgEnd(conn)                     → backfill the length word, advance outCount
```

`pqPutMsgEnd` (532) also tries `pqSendSome(conn, 0)` if outCount exceeds a threshold, to keep the kernel send buffer trickling for big messages. [verified-by-code, fe-misc.c:531-604]

### `pqReadData` — the heart of input

(605-823) Logic:

1. Left-justify buffer (memmove `inStart..inEnd` → offset 0).
2. If less than 8 KiB free at the tail, call `pqCheckInBufferSpace(inEnd + 8192, conn)` to enlarge.
3. Call `pqsecure_read` (TLS-aware). EINTR → retry; EAGAIN/EWOULDBLOCK → return 0; ECONNRESET → `definitelyFailed`.
4. If `nread > 0` and we got ≥ 32 KiB of "long message in progress" and another 8 KiB is free, **loop back to recv** without yielding. This is the "block-and-restart O(N²) defense": some kernels return only 1 packet per recv. [from-comment, fe-misc.c:691-705]
5. A `nread == 0` return is ambiguous — could be EOF or just nothing-now. Resolve via `pqReadReady` (poll/select). For TLS, can't trust select due to record buffering — just return 0 and let the next caller try `SSL_read` again. [from-comment, fe-misc.c:720-737]

### `pqSendSome`

(825-992) Writes from `outBuffer` to socket via `pqsecure_write`. On `EINTR` retries. On `EAGAIN`/non-blocking mode returns `1` (partial). On hard error sets `conn->write_failed = true` AND saves message in `conn->write_err_msg`, then clears `outBuffer` and **returns 0 anyway** — caller is expected to keep reading from the server because the server may have a clearer error than `EPIPE`. The deferred write-error reporting is a key idiom. [from-comment, fe-misc.c:807-823]

Also: while writing it may opportunistically call `pqReadData` to drain the socket if the kernel buffer is full, to avoid a write/read deadlock with the server.

### `pqGetInt` / `pqPutInt`

(216-285) Only 2-byte and 4-byte sizes are supported. **There is no `pqGetInt8`** at this layer — 8-byte ints (xact IDs in logical-replication messages, etc.) are read via two `pqGetInt(4)` calls or via direct `memcpy` + `pg_ntoh64`. The `default:` branch in the switch is a `pqInternalNotice` "integer of size %zu not supported" — programming error. [verified-by-code, fe-misc.c:215-285]

### `PQsocketPoll`

(1141-1232) Public; abstracts away the `poll(2)` vs `select(2)` choice. Takes `forRead`, `forWrite`, `end_time`. Returns >0 ready, 0 timeout, -1 error. Used by `pqSocketCheck` internally and by some applications.

### `pqWaitTimed`

(1034-1056) Blocks until socket is ready or `end_time` passes. `end_time = -1` means infinite. Combined with `pqSocketCheck` (1082) which calls `PQsocketPoll`. Returns 0 on ready, 1 on timeout, -1 on error.

## Invariants & gotchas

- **`pqGet*` and `pqPut*` return 0 on success, non-zero (`EOF`) on need-more-data or error.** Caller patterns: in the input parser, `if (pqGetInt(...)) return;` — the parser's outer loop will retry once more bytes arrive. [verified-by-code, fe-misc.c:215-285]
- **`pqGetInt` rejects sizes other than 2 and 4.** Cannot be used for 1-byte; use `pqGetc` for that. Cannot be used for 8-byte; consult the caller. [verified-by-code, fe-misc.c:215-247]
- **Input buffer can grow indefinitely.** `pqCheckInBufferSpace` only fails on `realloc` returning NULL or on integer overflow. A malicious server sending a 2 GiB message will succeed in allocating, then fail when the int32 multiplication overflows (`newsize > 0` guards). [verified-by-code, fe-misc.c:397-435] **There is no upper-bound enforcement on message size at this layer** — the validation `msgLength > 30000 && !VALID_LONG_MESSAGE_TYPE(id)` lives in fe-protocol3.c.
- **`pqSendSome` may opportunistically read.** Looking at the function in isolation, "send" appears synchronous; in practice it can advance `inEnd` as a side effect because the same socket round-trip handles both directions for TLS records and to avoid OS-level pipe-full deadlocks. [from-comment, fe-misc.c:817-823]
- **TLS `pqsecure_read` returning 0 is ambiguous.** Cannot rely on `select(2)` for SSL — SSL records buffer at OpenSSL's layer. The `#ifdef USE_SSL` branch in `pqReadData` returns 0 without consulting `pqReadReady`. [from-comment, fe-misc.c:734-739]
- **`pqReadData`'s `someread > 0` short-circuit.** After at least one successful `recv`, a subsequent EOF returns `1` ("got something then EOF") rather than `-1`. Lets parsers consume what's already buffered before reporting connection-closed. [from-comment, fe-misc.c:707-712]
- **`pqPutMsgStart` reserves space for the 4-byte length word**, not the 1-byte type. Type byte is written immediately if non-zero (startup messages pass type=0 to skip it). [verified-by-code, fe-misc.c:472-507]
- **`pqFlush` returns 1 on "wrote some but not all"** in non-blocking mode. Callers must distinguish 0 (done) / 1 (would block) / -1 (error). Misuse — treating 1 as success — silently drops data still queued in outBuffer. [verified-by-code, fe-misc.c:993-1017]
- **`PQmblen` is process-global encoding-agnostic**: it does NOT consult a `PGconn` — it operates on the encoding parameter. Multibyte length is a property of the byte stream + named encoding, not of the connection. [verified-by-code, fe-misc.c:1254-1284]

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-secure.c.md` — `pqsecure_read`/`pqsecure_write` (the TLS-aware bytestream backing pqReadData/pqSendSome).
- `knowledge/files/src/interfaces/libpq/fe-protocol3.c.md` — the parser that drives every `pqGet*` here.
- `knowledge/files/src/interfaces/libpq/libpq-int.h.md` — buffer field definitions.
- Backend counterpart: `knowledge/files/src/backend/libpq/pqcomm.c.md` (server-side mirror of these primitives).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Invariants for INV tagging

**INV-libpq-misc-1**: Input buffer left-justification at `pqReadData` and `pqCheckInBufferSpace` means `inStart`, `inCursor`, `inEnd` may all jump back to lower addresses between two `pqGet*` calls. Any caller holding a pointer into `inBuffer` across an I/O step has a dangling pointer. [verified-by-code, fe-misc.c:351-385, 610-625]

**INV-libpq-misc-2**: `pqGet*` advance `inCursor` only on success; on EOF return they leave `inCursor` where it was. The parser uses `conn->inCursor = conn->inStart` at message start (fe-protocol3.c:84) to rewind after partial parse. [verified-by-code, fe-misc.c:77-213 across all pqGet*]

**INV-libpq-misc-3**: `pqPutMsgStart` requires a corresponding `pqPutMsgEnd` before the next `pqPutMsgStart`. There is no nesting. The state variable is `outMsgStart`; double-start would clobber it. Not asserted, just convention. [inferred, fe-misc.c:472-541]

## Potential issues

- **[ISSUE-correctness: no upper bound on `pqCheckInBufferSpace`]** fe-misc.c:351-440 — apart from int32 overflow at ~2 GiB, there's no defended ceiling. A server (or MITM if no TLS) can force libpq to allocate gigabytes by sending a huge message length. The protocol-layer check `msgLength > 30000 && !VALID_LONG_MESSAGE_TYPE(id)` (fe-protocol3.c:100) is the actual ceiling, but it's not enforced here. **Severity: maybe.** Phase D should consider a libpq-level hard cap.
- **[ISSUE-correctness: `pqGetInt(4)` returns signed int**] fe-misc.c:230-237 — `*result = (int) pg_ntoh32(tmp4)`. A high-bit-set length on the wire would become negative when stored as `int`. Callers (e.g. msgLength) do check for `< 4`. Worth verifying every site does so. **Severity: maybe.**
- **[ISSUE-undocumented-invariant: write-error deferral]** fe-misc.c:807-823 — `pqSendSome` setting `conn->write_failed` but returning 0 means a subsequent call won't necessarily re-attempt. The error surfaces only after the next read succeeds in pulling a server error. Documented in the function header but worth a corpus tag.
- **[ISSUE-style: hand-rolled `select(2)` / `poll(2)` dispatch]** fe-misc.c:1140-1232 — `PQsocketPoll` reimplements logic that backend latch code now does centrally. Acceptable because libpq must not depend on backend code, but a periodic sync-with-backend review would be wise.
- **[ISSUE-question: signal-safety of `pqReadData`]** fe-misc.c:605-823 — uses `malloc/realloc` via `pqCheckInBufferSpace`. Is libpq EVER expected to call it from a signal context? `PQcancel` is the only signal-safe API, and it avoids this whole layer. Document the assumption explicitly. **Severity: nit.**
- **[ISSUE-correctness: 32 KiB "long message" threshold is hardcoded]** fe-misc.c:704 — the constant tunes O(N²) avoidance for big messages but interacts with kernel send-buffer sizes and 9P/whatever weird transports. Worth a tunable? **Severity: nit.**

## Tally

`[verified-by-code]=12 [from-comment]=6 [from-readme]=0 [inferred]=1 [unverified]=0`
