---
path: src/interfaces/libpq/fe-cancel.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 793
depth: deep
---

# fe-cancel.c

- **Source path:** `source/src/interfaces/libpq/fe-cancel.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 793
- **Companion files:** `libpq-int.h` (PGconn, SockAddr, CancelRequestPacket), `fe-connect.c` (pqMakeEmptyPGconn, pqConnectDBStart, pqConnectDBComplete, PQconnectPoll — reused by the modern cancel path), `fe-misc.c` (pqPutMsgStart/End/pqFlush — used by `PQsendCancelRequest`)

## Purpose

Client-side query cancellation. Two parallel APIs live here:

1. **The modern `PGcancelConn` flow** (PG ≥ 17): `PQcancelCreate` → either `PQcancelBlocking` or `PQcancelStart`+`PQcancelPoll` → `PQcancelFinish`. Reuses the full connect state machine in `fe-connect.c` so it can do TLS, GSS, and multi-host the same way a normal connection would. Sends the cancel as a real `CancelRequest` protocol message over an authenticated channel. [verified-by-code, fe-cancel.c:60-365]
2. **The legacy `PGcancel` flow**: `PQgetCancel(conn)` → `PQcancel(cancel, ...)` (signal-safe) → `PQfreeCancel`. Hand-rolled `socket()`+`connect()`+`send()`+`recv()` with raw cancel packet. Plus the even older `PQrequestCancel(conn)` (not thread-safe, kept for compatibility). [from-comment, fe-cancel.c:537-548, 740-755]

## Public API surface

| Function | Line | One-liner |
|---|---|---|
| `PQcancelCreate` | 68 | Allocate a `PGcancelConn` cloning host/port/cancel-key from an open conn. |
| `PQcancelBlocking` | 190 | Blocking cancel via the modern state machine. |
| `PQcancelStart` | 204 | Begin async cancel; caller polls. |
| `PQcancelPoll` | 226 | Drive the cancel-conn state machine; ends in waiting-for-EOF after sending. |
| `PQcancelStatus` | 302 | Wraps `conn->status`. |
| `PQcancelSocket` | 313 | Wraps `PQsocket` on the underlying conn. |
| `PQcancelErrorMessage` | 325 | Wraps `PQerrorMessage`. |
| `PQcancelReset` | 337 | Reset a `PGcancelConn` so it can be re-used. |
| `PQcancelFinish` | 353 | Free a `PGcancelConn`. |
| `PQgetCancel` | 368 | Legacy: snapshot host + cancel key into a static `PGcancel`. |
| `PQsendCancelRequest` | 472 | Internal-ish: build+send the CancelRequest message on the new conn the state machine just created. |
| `PQfreeCancel` | 502 | Legacy: free a `PGcancel`. |
| `PQcancel` | 548 | Legacy: blocking signal-safe cancel via raw socket. |
| `PQrequestCancel` | 752 | Legacy++: not thread-safe; writes to `conn->errorMessage` on failure. |

## Internal landmarks

### Two backing structs

```c
struct pg_cancel_conn { PGconn conn; };               // wrapper just to keep type-safety
struct pg_cancel {                                    // legacy snapshot of cancel info
    SockAddr   raddr;                                 // remote addr
    int        be_pid;
    int        pgtcp_user_timeout;
    int        keepalives, keepalives_idle, keepalives_interval, keepalives_count;
    int32      cancel_pkt_len;                        // network byte order
    char       cancel_req[FLEXIBLE_ARRAY_MEMBER];     // CancelRequestPacket
};
```
[verified-by-code, fe-cancel.c:30-55]

The flexible array is sized at allocation: `offsetof(PGcancel, cancel_req) + offsetof(CancelRequestPacket, cancelAuthCode) + conn->be_cancel_key_len`. Cancel-key length is variable per protocol-3 BackendKeyData. [verified-by-code, fe-cancel.c:401-403, 460-470]

### Modern flow (PQcancelCreate → PQcancelBlocking)

`PQcancelCreate` clones the underlying conn's host (only the *currently used* host, not the full multi-host list), copies the cancel key, and sets `cancelConn->status = CONNECTION_ALLOCATED`. `cancelRequest = true` is set on the PGconn so `PQconnectPoll` skips the multi-host loop and the `target_server_type` retry pass. [verified-by-code, fe-cancel.c:67-186]

`PQcancelBlocking` is literally `PQcancelStart` + `pqConnectDBComplete`. `PQcancelStart` checks status, then calls `pqConnectDBStart`. The state machine in `PQconnectPoll` does the normal `CONNECTION_NEEDED → MADE → AWAITING_RESPONSE` dance; the only divergence is in `PQcancelPoll` itself — once `CONNECTION_AWAITING_RESPONSE` is reached the cancel poll function takes over and just waits for the server to close the connection (its way of saying "got the cancel"). [verified-by-code, fe-cancel.c:189-300]

### Legacy `PQcancel` (signal-safe path)

This is the hand-rolled one. Constraints, per the head comment at fe-cancel.c:540-547:

- Must be callable from a signal handler. **No `malloc/free` and no `sprintf` allowed.** Error messages are built with `strcpy`/`strcat`/explicit decimal-digit unrolling.
- `errno` is saved/restored.
- `setsockopt` for keepalives is wrapped in `optional_setsockopt` (516) so a missing option doesn't fail the cancel.
- The send→recv pattern: `connect` → `send(cancel_req)` → `recv(1 byte)` and wait for EOF. The recv is solely to synchronize: it ensures the postmaster has processed the cancel before the caller issues another command on the original conn. [verified-by-code, fe-cancel.c:660-695]
- `retry3:`/`retry4:`/`retry5:` labels each handle `EINTR` restart on connect, send, recv.

## Invariants & gotchas

- **`PQcancel` (legacy) IS async-signal-safe; `PQrequestCancel` is NOT.** The whole point of the `PGcancel` snapshot was to make the actual cancel safe to call from `SIGINT`. `PQrequestCancel` writes into `conn->errorMessage` and so cannot be re-entered from a signal handler. [from-comment, fe-cancel.c:537-547, 740-748]
- **`PQcancel` cannot translate the error string** — it writes decimal `errno` instead of `strerror(errno)`, because `strerror` is not signal-safe. So errbufs in user code reading "error 32" mean errno 32 (broken pipe). [from-comment, fe-cancel.c:710-728]
- **`PQgetCancel` may return a dummy zero-filled object** if the server did not send a cancel key. Calling `PQcancel` on it returns false with "PQcancel() -- no cancellation key received". This odd dual-meaning return is kept because changing it would break old clients. [from-comment, fe-cancel.c:380-401]
- **The modern flow re-runs SSL/GSS/auth** on the cancel conn — meaning a cancel can be denied by `pg_hba.conf` rejecting the auth, can fail TLS handshake, etc. This is the point: protocol-3 cancellation was historically unauthenticated and trivially spoofable by anyone who could reach the listener. The new flow makes cancels first-class authenticated requests. The legacy `PQcancel` retains the old unauthenticated behavior for backward compat. [inferred from fe-cancel.c:226-300 + protocol message structure]
- **`PQcancelReset` puts a `PGcancelConn` back in `CONNECTION_ALLOCATED`** without freeing the cloned host info, so the same target can be cancelled multiple times in sequence. `PQcancelStart` rejects a non-ALLOCATED state with "cancel request is already being sent on this connection". [verified-by-code, fe-cancel.c:204-217, 337-365]
- **Cancel-request packet format** is `int32 length | int32 CANCEL_REQUEST_CODE | int32 backendPID | bytes cancelKey`. Length includes itself. `CANCEL_REQUEST_CODE` is a magic version that tells the postmaster "this is not a startup". [verified-by-code, fe-cancel.c:450-468, 478-498]
- **Keepalive socket-options are applied to the cancel socket too**, copied from the connection's settings. Without these, `PQcancel` could block forever if the postmaster machine is wedged. [from-comment, fe-cancel.c:594-600]

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-connect.c.md` — `PQconnectPoll` state machine that the modern cancel reuses.
- `knowledge/files/src/interfaces/libpq/libpq-int.h.md` — PGconn fields `be_pid`, `be_cancel_key`, `be_cancel_key_len`, `cancelRequest`.
- Backend counterpart: `knowledge/files/src/backend/postmaster/postmaster.c.md` (the cancel-request branch of the connection acceptor) and `knowledge/files/src/backend/storage/ipc/procsignal.c.md` (delivers SIGINT to the target backend).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: unauthenticated `PQcancel` packet sent in cleartext]** fe-cancel.c:548-735 — the legacy path opens a raw socket and writes the cancel request without TLS. Even when the original connection was over TLS, a cancel travels in the clear. The cancel-key proves liveness but the very fact of cancellation (and the backend PID) leaks to a network observer. **Severity: maybe.** Documented as an intentional historical compatibility surface; the modern `PGcancelConn` path is the fix.
- **[ISSUE-correctness: cancel-key forging surface]** fe-cancel.c:660-695 — the cancel-key is sent as opaque bytes. Server-side acceptance is a memcmp against the live PGPROC's key. If `be_cancel_key_len` is short and predictable, key brute-force is on the table. Protocol-3 widened the key to defend this; the older 4-byte key is still accepted for old clients. **Severity: maybe.** Phase D should verify minimum key length policy.
- **[ISSUE-undocumented-invariant: legacy `PQgetCancel` returns dummy on missing key]** fe-cancel.c:382-398 — the dual-meaning return of "a calloc'd PGcancel with cancel_pkt_len==0 is a dummy" is recognized only inside `PQcancel`. Callers writing `if (cancel == NULL)` will not distinguish "out of memory" from "no cancel possible"; both reasonable. The comment explicitly chooses this. Worth a corpus tag.
- **[ISSUE-style: hand-rolled decimal-to-string in error path]** fe-cancel.c:712-727 — `do { *(--bufp) = (val % 10) + '0'; val /= 10; } while (val > 0)`. Correct (signal-safe), but flag for review if anyone tries to "modernize" with `snprintf` — that would break the signal-safety contract.
- **[ISSUE-question: re-entry into `PQcancelStart` on a wedged cancelConn]** fe-cancel.c:208-217 — checks for `CONNECTION_BAD` and refuses, also refuses if not `CONNECTION_ALLOCATED`. The intent is good but if the cancel got stuck mid-handshake (`AWAITING_RESPONSE`), the caller must `PQcancelReset` first. Not all errors paths set BAD; check the failure modes in `PQcancelPoll`. **Severity: nit.**
- **[ISSUE-leak: cancel-conn errorMessage carries the underlying conn's host info]** fe-cancel.c:67-186 — on cancel-conn alloc the host is `strdup`'d from the original conn. If the cancel fails, `PQcancelErrorMessage` will name the host, which is the same as the user-facing host. Not a leak proper; flag as a thing data-leak audits should expect.

## Tally

`[verified-by-code]=10 [from-comment]=6 [from-readme]=0 [inferred]=1 [unverified]=0`
