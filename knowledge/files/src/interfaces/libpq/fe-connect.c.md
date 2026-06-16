---
path: src/interfaces/libpq/fe-connect.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 8428
depth: deep
---

# fe-connect.c

- **Source path:** `source/src/interfaces/libpq/fe-connect.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 8428
- **Companion files:** `libpq-int.h` (PGconn definition, ConnStatusType, pg_conn_host), `libpq-fe.h` (public types), `fe-auth.c` (auth dispatch called from PQconnectPoll), `fe-secure.c` (SSL/GSS negotiation), `fe-protocol3.c` (`pqBuildStartupPacket3`, `pqGetNegotiateProtocolVersion3`), `fe-cancel.c` (reuses pqMakeEmptyPGconn / pqConnectDBStart for cancel paths)

## Purpose

The big one. Owns the entire client-side connection lifecycle: connection-string / URI / service-file / array-of-keywords parsing, default lookup (env vars, pgpass, sslmode/gssencmode negotiation precedence), multi-host iteration, async DNS, the giant `PQconnectPoll` state machine, accessors for all read-only PGconn fields, and the teardown via `PQfinish`/`pqClosePGconn`. Also contains the ldap service-lookup, the `.pg_service.conf` parser, and the `.pgpass` lookup. [from-comment, fe-connect.c:1-13]

## Top-of-file structure

The file has no single top-of-file comment block beyond the IDENTIFICATION header; it is organized by ~15 internal section comments (search for `/* =====` and `/* ---`). Major sections:

1. Defaults table `PQconninfoOptions[]` (~lines 200-450) — the canonical list of every keyword libpq understands (host, hostaddr, port, dbname, user, password, sslmode, gssencmode, sslrootcert, channel_binding, target_session_attrs, …). The `dispchar` field controls whether psql echoes it.
2. URI / conninfo / service / array parsers (`conninfo_parse`, `conninfo_uri_parse`, `parseServiceInfo`, `conninfo_array_parse`, `PQconninfoParse`).
3. `pqMakeEmptyPGconn` (4991) / `freePGconn` (5091) — allocation + destruction.
4. The connection establishment trio: `pqConnectDBStart` (2721) → `PQconnectPoll` (2925) → `pqConnectDBComplete` (2799), used by both blocking `PQconnectdb` and async `PQconnectStart`.
5. The 30-plus `PQ*` getters: `PQdb`, `PQuser`, `PQhost`, `PQport`, `PQstatus`, `PQparameterStatus`, `PQbackendPID`, `PQprotocolVersion`, `PQfullProtocolVersion`, `PQserverVersion`, `PQerrorMessage`, `PQsocket`, `PQpipelineStatus`, `PQconnectionUsedPassword`, `PQconnectionUsedGSSAPI`, etc. (lines 7575-7831). Each is 3-15 lines, all ABI-frozen.

## Public API surface

Every PQ\* function below is exported in `exports.txt` and ABI-frozen across major versions.

| Function | Line | One-liner |
|---|---|---|
| `PQconnectdbParams` | 775 | Blocking connect, keyword/value arrays. |
| `PQconnectdb` | 830 | Blocking connect, single conninfo string. |
| `PQconnectStartParams` | 877 | Async connect — returns immediately; caller polls. |
| `PQconnectStart` | 958 | Async connect, single conninfo string. |
| `PQconnectPoll` | 2925 | The state-machine driver; ~1800 lines. |
| `PQpingParams` / `PQping` | 793, 846 | Run a connection attempt purely to ask "is the server up?". |
| `PQconndefaults` | 2210 | Return the defaults table as `PQconninfoOption[]`. |
| `PQconninfo` | 7519 | Return effective options *of an already-connected* PGconn. |
| `PQconninfoParse` | 6279 | Parse a conninfo string without connecting. |
| `PQconninfoFree` | 7563 | Free a `PQconninfoOption *`. |
| `PQsetdbLogin` | 2248 | Legacy positional-arg connect. |
| `PQfinish` | 5354 | Close + free a PGconn. |
| `PQreset` | 5368 / `PQresetStart` 5401 / `PQresetPoll` 5420 | Tear-down + reconnect-in-place. |
| `PQdb` 7576 / `PQuser` 7584 / `PQpass` 7592 / `PQhost` 7609 / `PQhostaddr` 7632 / `PQport` 7645 / `PQtty` 7663 / `PQoptions` 7671 | Getters. `PQtty` is a no-op for ABI compat. [verified-by-code, fe-connect.c:7662-7669] |
| `PQstatus` 7679 / `PQtransactionStatus` 7687 / `PQparameterStatus` 7697 | Connection-level state. |
| `PQprotocolVersion` 7712 / `PQfullProtocolVersion` 7722 / `PQserverVersion` 7732 | Wire protocol + server version. |
| `PQerrorMessage` 7742 | Persistent buffer (`conn->errorMessage.data`); overwritten on next error. |
| `PQsocket` 7768 | Returns -1 (never positive-unsigned) even on Windows. [from-comment, fe-connect.c:7752-7765] |
| `PQbackendPID` 7778 / `PQpipelineStatus` 7786 | |
| `PQconnectionNeedsPassword` 7795 / `PQconnectionUsedPassword` 7810 / `PQconnectionUsedGSSAPI` 7821 | Auth flags. |
| `PQclientEncoding` 7832 / `PQsetClientEncoding` 7840 | |
| `PQsetErrorVerbosity` 7882 / `PQsetErrorContextVisibility` 7894 | Format toggles for `PQerrorMessage`. |
| `PQsetNoticeReceiver` 7906 / `PQsetNoticeProcessor` 7923 | Install caller-supplied notice hook. |
| `PQregisterThreadLock` 8411 / `PQgetThreadLock` 8424 | App-supplied mutex around `getpwuid`/etc. |

## Internal landmarks

### Multi-host iteration

`PGconn` carries `connhost[]` (an array of `pg_conn_host` entries, each with `host`, `hostaddr`, `port`, `password`) plus `nconnhost`, `whichhost`, `try_next_host`, `try_next_addr`. `PQconnectPoll` loops the state machine over each host, then over each resolved address within that host. The `keep_going:` label (fe-connect.c:2986) is the loop head; `try_next_host = true` causes the next `PQconnectPoll` cycle to drop addrinfo and call `pg_getaddrinfo_all` for the next entry. [verified-by-code, fe-connect.c:2986-3070]

### Connection state machine (PQconnectPoll)

The `ConnStatusType` enum (`libpq-fe.h`) drives the machine. Transitions, in normal-path order:

```
CONNECTION_NEEDED                 (initial; about to socket(2)+connect(2))
  ↓ socket + non-blocking connect
CONNECTION_STARTED                (connect(2) in flight)
  ↓ connect succeeded
CONNECTION_MADE                   (socket connected; about to send startup or SSL request)
  ↓ send startup / SSL request
CONNECTION_AWAITING_RESPONSE      (waiting for server's first reply byte)
  ↓ SSL handshake states: CONNECTION_SSL_STARTUP, CONNECTION_GSS_STARTUP
  ↓ auth round-trips: CONNECTION_AUTHENTICATING
CONNECTION_AUTH_OK                (got AuthenticationOk; absorbing post-auth msgs)
  ↓ may go to CONNECTION_CHECK_TARGET / CHECK_WRITABLE / CHECK_STANDBY
  ↓   if target_session_attrs needs a SHOW transaction_read_only round-trip
  ↓ may go to CONNECTION_CONSUME (drain any remaining startup messages)
CONNECTION_OK                     (steady state)
```

Failure goes via `error_return:` (fe-connect.c) → `connectFailureMessage` → state set to `CONNECTION_BAD`. The `keep_going` label allows fallthrough to retry the next host/address without yielding to the caller. [verified-by-code, fe-connect.c:2924-3070]

### Encryption negotiation

`init_allowed_encryption_methods` (4747), `select_next_encryption_method` (4852), `encryption_negotiation_failed` (4812). Implements the precedence `gssencmode > sslmode`, with fallback paths if e.g. `sslmode=prefer` fails the SSL handshake — the state machine drops to plaintext and retries from `CONNECTION_NEEDED`. The "had we ever a usable connection?" tracking decides whether silent fallback is safe. [verified-by-code, fe-connect.c:4746-4924]

### Conninfo / URI / service / array parsing

- `conninfo_parse` (6394) — key=value form.
- `conninfo_uri_parse` (6863) → `conninfo_uri_parse_options` (6916) → `conninfo_uri_parse_params` (7157) → `conninfo_uri_decode` (7290). Implements RFC-3986-ish `postgresql://user:pass@host:port/db?opt=val`. `%`-decoding uses `get_hexdigit` (7390).
- `conninfo_array_parse` (6570) — keywords/values pair-array form.
- `parseServiceInfo` (5992) → `parseServiceFile` (6064) — reads `~/.pg_service.conf` or `$PGSERVICEFILE`. Supports `[section]` headers; first match wins.
- `ldapServiceLookup` (5514) — fetches a service definition from LDAP if URI starts with `ldap://`.
- `conninfo_storeval` (7437) / `conninfo_getval` (7411) / `conninfo_find` (7501) — common store/lookup over a `PQconninfoOption[]`.
- `conninfo_add_defaults` (6728) — overlay environment defaults (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGSERVICE`, etc.).

### `.pgpass`

`passwordFromFile` (8015) opens `~/.pgpass` (or `$PGPASSFILE`), scans for the first `host:port:db:user:password` line whose first four fields match (with `*` wildcards). `pwdfMatchesString` (7973) handles `\:`/`\\` escapes. Used during connect when no password was supplied. [verified-by-code, fe-connect.c:7972-8166] File-mode check rejects world-readable pgpass on Unix.

### PGconn lifecycle

```
pqMakeEmptyPGconn  (4991)   →   alloc + defaults
  ↓
pqConnectDBStart    (2721)  →   set status = CONNECTION_NEEDED, kick PQconnectPoll once
  ↓
PQconnectPoll       (2925)  →   drives to CONNECTION_OK or CONNECTION_BAD
  ↓
... use ...
  ↓
pqClosePGconn       (5307)  →   sendTerminateConn (5273) + pqDropConnection
  ↓
freePGconn          (5091)  →   free every owned buffer + addrinfo + conn->pstatus list
```

`pqDropConnection` (537) closes the socket and resets in/out buffers; called on both clean shutdown and recoverable error mid-handshake. `pqReleaseConnHosts` (5190) and `release_conn_addrinfo` (5259) free the host/addrinfo arrays.

## Invariants & gotchas

- **`PQerrorMessage` is owned by libpq**, points into `conn->errorMessage.data` (a `PQExpBuffer`). Lifetime = until next libpq call that resets it, or until `PQfinish`. Callers MUST NOT free it. If the buffer is marked "broken" (allocation failure), the function returns a static "out of memory\n" string. [verified-by-code, fe-connect.c:7741-7765]
- **`PQsocket` returns -1 for any invalid socket** even on Windows where the underlying `INVALID_SOCKET` is `~0`. The conversion happens here so that the ABI is uniform across platforms. [from-comment, fe-connect.c:7747-7765]
- **PGconn is thread-private.** libpq is thread-safe only across distinct connections. Two threads using the same PGconn simultaneously is undefined behavior — there is no internal locking on `conn->status`, `conn->result`, etc. [from-comment, fe-connect.c:8395-8410]
- **`conn->status == CONNECTION_BAD` after `PQconnectdb` does not free the PGconn.** Callers must always `PQfinish` even when `PQstatus(conn) == CONNECTION_BAD`. The blurb at fe-connect.c:768-782 documents this. Missing the `PQfinish` is a classic libpq client leak.
- **Re-entry into `PQconnectPoll` after a `default:` fallthrough sets "memory corruption" error.** The check at fe-connect.c:2979 catches a caller polling with a status it shouldn't; it does *not* recover, it just fails. [verified-by-code, fe-connect.c:2978-2981]
- **`target_server_type = prefer-standby` re-runs the host list with `PASS2`** if no standby was found, by setting `target_server_type = SERVER_TYPE_PREFER_STANDBY_PASS2` and resetting `whichhost = 0`. Cancel requests bypass this. [verified-by-code, fe-connect.c:3009-3024]
- **Backend cancellation key length is variable.** Stored as `conn->be_cancel_key` + `conn->be_cancel_key_len`; in older protocols this was a fixed 4 bytes, but the protocol-3 BackendKeyData now carries a length. `fe-cancel.c` builds a packet of `offsetof(CancelRequestPacket, cancelAuthCode) + be_cancel_key_len`. [verified-by-code, fe-cancel.c:401-403, 460-470]
- **`pg_link_canary_is_frontend` is called at `pqConnectDBStart`** to detect a build where libpq's `src/common` files got linked against the backend versions; failure is a fatal config error, not translated because only developers should ever see it. [from-comment, fe-connect.c:2728-2737]
- **Service-file parsing is permissive.** `parseServiceFile` ignores unknown keywords with no error; this is intentional for forward-compat but means a typo silently does nothing. [verified-by-code, fe-connect.c:6063-6277]
- **URI parsing percent-decodes the userinfo password.** A password with raw `:` in `.pg_service.conf` works (no decoding); the same password in the URI must be `%3A`-encoded. [verified-by-code, fe-connect.c:7289-7388]

## Cross-refs

- Public header: `knowledge/files/src/interfaces/libpq/libpq-fe.h.md` (when written).
- Private header: `knowledge/files/src/interfaces/libpq/libpq-int.h.md` (PGconn struct layout, async state enums).
- Auth: `knowledge/files/src/interfaces/libpq/fe-auth.c.md` and `fe-auth-scram.c.md`.
- TLS: `knowledge/files/src/interfaces/libpq/fe-secure.c.md` and `fe-secure-openssl.c.md`.
- Wire protocol counterpart in backend: `knowledge/files/src/backend/libpq/pqcomm.c.md`, `knowledge/files/src/backend/libpq/auth.c.md`, `knowledge/files/src/backend/postmaster/postmaster.c.md` (the listener side of multi-host connect).
- Subsystem doc: `knowledge/subsystems/libpq.md` (when written).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: silent sslmode downgrade on connect failure]** `fe-connect.c:4836-4924` — `connection_failed` + `select_next_encryption_method` may step from `sslmode=prefer`/SSL handshake failure to plaintext without surfacing why to the application. The only signal is `PQconnectionUsedGSSAPI`/`PQparameterStatus("ssl_in_use")` after the fact. **Severity: maybe.** Not a leak in the network sense, but a real surface for "I thought SSL was on": clients defaulting to `sslmode=prefer` (the default!) get plaintext on a misconfigured server with no warning. Important for Phase D data-leak hardening.
- **[ISSUE-question: pgpass file world-readable check is a `stat(2)` race]** `passwordFromFile` (8015) — the file-mode check and the open are not atomic. A symlink swap between stat and open could bypass the world-readable rejection on some platforms. **Severity: maybe.** Likely defended by the fact that `.pgpass` lives in `$HOME` which only the user has write access to.
- **[ISSUE-stale-todo: `PQtty` no-op kept for ABI]** fe-connect.c:7662-7669 — comment says "No longer does anything, but the function remains for API backwards compatibility." Documented; flag only for cleanup audits.
- **[ISSUE-doc-drift: `getCancel` dummy-object path]** `fe-cancel.c:382-398` — `PQgetCancel` returns a `calloc(1, sizeof(PGcancel))` "dummy" object when the server didn't send a cancel key (e.g. very old server). `PQcancel` recognizes it via `cancel_pkt_len == 0` and refuses with a clear error. The comment explains the reason (callers can't distinguish OOM from "no cancel possible") but this dual-meaning return value is an easy mistake to copy.
- **[ISSUE-undocumented-invariant: `conn->errorMessage` lifetime across `PQreset`]** `PQreset` calls `pqClosePGconn` which calls `pqDropConnection`; these reset internal buffers but `conn->errorMessage` survives so the application can read what just failed before pollign the reset. Not commented anywhere; corpus-side note. **Severity: nit.**
- **[ISSUE-correctness: `pg_getaddrinfo_all` failure logs into errorMessage but loops on**] fe-connect.c:3060-3070 — DNS failure for one host appends to `conn->errorMessage` and continues to next host. If every host fails the application sees a concatenated multi-error blob. Intentional (per surrounding code) but a leak surface for hostname enumeration if errors are logged verbatim. **Severity: maybe.** Phase D should review.
- **[ISSUE-question: `requirepeer` enforcement timing]** Verify when `requirepeer` (Unix-socket peer credential check) actually fires in the state machine. Not visible from grep above; flag for the auth-side doc.
- **[ISSUE-leak: `cancelConn->connhost[0].password` strdup'd, never owned-flag set]** `fe-cancel.c:373-377` — strdup on connect; on OOM jumps to `oom_error` without freeing prior allocations? The cancelConn will be freed via `PQcancelFinish` → `freePGconn` which iterates connhost; needs a once-over to confirm `connhost[i].password` is in the `free()` list. **Severity: maybe.** Flag for a focused read of `freePGconn` (line 5091).

## Tally

`[verified-by-code]=14 [from-comment]=8 [from-readme]=0 [inferred]=0 [unverified]=2`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new libpq protocol message](../../../../scenarios/add-new-protocol-message.md)

<!-- scenarios:auto:end -->
