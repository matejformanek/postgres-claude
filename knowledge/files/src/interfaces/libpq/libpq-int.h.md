# libpq-int.h

- **Source path:** `source/src/interfaces/libpq/libpq-int.h`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 985 lines

## Purpose

> "This file contains internal definitions meant to be used only by the frontend libpq library, not by applications that call it." [`libpq-int.h:3-5`, from-comment]
>
> "An application can include this file if it wants to bypass the official API defined by libpq-fe.h, but code that does so is much more likely to break across PostgreSQL releases than code that uses only the official API." [`libpq-int.h:7-10`, from-comment]

The implementation header: defines the **full** `struct pg_conn` (PGconn) and `struct pg_result` (PGresult), the async state machine enum, and every `pqXxx` internal function prototype shared across libpq's .c files. ABI-internal — symbols starting `pq` (lowercase) are libpq-internal; `PQ` is the public API.

## Subsidiary types

- `PGresult_data` (lines 99-105) — union for variable-length subsidiary storage blocks attached to a PGresult; `next` link + `space[1]` flexible-array trick. fe-exec.c manages these as a linked list of slabs.
- `pgresParamDesc` (lines 108-111) — `Oid typid` per param.
- `PGresAttValue` (lines 133-137) — `len` + `char *value`. **NULL is encoded** as `len == NULL_LEN` (-1) and all NULL attrs in a result share one `null_field[1]` zero byte (struct field at line 199). [verified-by-code]
- `PGMessageField` (lines 140-145) — linked list, `code` (single byte field code from PG protocol: 'S', 'M', 'D', etc.) + FLEXIBLE_ARRAY_MEMBER `contents`.
- `PGNoticeHooks` (lines 148-154) — `noticeRec` + `noticeRecArg`, `noticeProc` + `noticeProcArg`. Copied from PGconn into each PGresult so result-bound notice processing doesn't deref the conn.
- `PGEvent` (lines 156-163) — `proc`, copied `name` (for error msgs), `passThrough`, `data`, `resultInitialized` flag. See `libpq-events.c` doc.

## PGresult struct (lines 165-211)

Fields, grouped:

- Tuple data: `ntups`, `numAttributes`, `attDescs`, `tuples` (array of arrays of `PGresAttValue`), `tupArrSize`.
- Params: `numParameters`, `paramDescs`.
- Status: `resultStatus`, `cmdStatus[CMDSTATUS_LEN]` (64 bytes, matches backend `COMPLETION_TAG_BUFSIZE`), `binary` (0 = text, 1 = binary).
- Copied-from-conn at creation: `noticeHooks`, `events`, `nEvents`, `client_encoding`.
- Error: `errMsg`, `errFields` (linked list), `errQuery`.
- The shared `null_field[1]` null byte.
- Slab allocator: `curBlock`, `curOffset`, `spaceLeft`, `memorySize`.

Note `tuples` is a **separately** malloc'd block (so it can realloc independently), while attDescs and the error fields point into the slab chain. [verified-by-code at lines 201-210, from-comment]

## State-machine enums

- `PGAsyncStatusType` (lines 213-227): `PGASYNC_IDLE`, `BUSY`, `READY`, `READY_MORE`, `COPY_IN`, `COPY_OUT`, `COPY_BOTH`, `PIPELINE_IDLE`.
- Encryption-method bitmask (lines 229-233): `ENC_ERROR` 0, `ENC_PLAINTEXT` 0x01, `ENC_GSSAPI` 0x02, `ENC_SSL` 0x04 — for `allowed_enc_methods`/`failed_enc_methods`/`current_enc_method`.
- `PGTargetServerType` (lines 236-245): decoded `target_session_attrs`. Has a `SERVER_TYPE_PREFER_STANDBY_PASS2` for the two-pass scan over hosts.
- `PGLoadBalanceType` (lines 248-252): `LOAD_BALANCE_DISABLE`/`RANDOM`.
- `PGTernaryBool` (lines 255-260): unknown/yes/no for GUCs we may have to round-trip.
- `pg_conn_host_type` (lines 309-314): `CHT_HOST_NAME`/`CHT_HOST_ADDRESS`/`CHT_UNIX_SOCKET`.
- `PGQueryClass` (lines 320-328): `PGQUERY_SIMPLE/EXTENDED/PREPARE/DESCRIBE/SYNC/CLOSE`.

## Auth-response markers (lines 337-340)

Internal byte tags so `fe-trace.c` can disambiguate protocol-byte-'p' messages: `AUTH_RESPONSE_GSS` 'G', `AUTH_RESPONSE_PASSWORD` 'P', `AUTH_RESPONSE_SASL_INITIAL` 'I', `AUTH_RESPONSE_SASL` 'S'.

## Command queue + host

- `PGcmdQueueEntry` (lines 345-350) — singly-linked queue: `queryclass`, `query` (or NULL on OOM), `next`. PGconn holds head/tail/recycle pointers (lines 492-499).
- `pg_conn_host` (lines 357-367) — per-host state from comma-split conninfo: `type`, `host`, `hostaddr`, `port`, `password` (read from password file).

## PGconn struct (lines 373-691)

The big one. Field categories:

**Saved connection options** (lines 376-434, all `char *`): `pghost`, `pghostaddr`, `pgport`, `connect_timeout`, `pgtcp_user_timeout`, `client_encoding_initial`, `pgoptions`, `appname`, `fbappname`, `dbName`, `replication`, `pgservice`, `pgservicefile`, `pguser`, **`pgpass`**, **`pgpassfile`**, `channel_binding`, `keepalives*` (4 fields), `sslmode`, `sslnegotiation`, `sslcompression`, `sslkey`, `sslcert`, **`sslpassword`** (client key passphrase), `sslcertmode`, `sslrootcert`, `sslcrl`, `sslcrldir`, `sslsni`, `requirepeer`, `gssencmode`, `krbsrvname`, `gsslib`, `gssdelegation`, `min_protocol_version`, `max_protocol_version`, `ssl_min_protocol_version`, `ssl_max_protocol_version`, `target_session_attrs`, `require_auth`, `load_balance_hosts`, **`scram_client_key`**, **`scram_server_key`**, `sslkeylogfile`.

**OAuth state** (lines 440-450): `oauth_issuer`, `oauth_issuer_id`, `oauth_discovery_uri`, `oauth_client_id`, **`oauth_client_secret`**, `oauth_scope`, **`oauth_token`** (bearer), `oauth_ca_file`, `oauth_want_retry`.

**Cancel/trace** (lines 436, 452-454): `cancelRequest`, `Pfdebug` (FILE* trace), `traceFlags`.

**Hooks** (lines 456-462): `noticeHooks`, `events[]` array with `nEvents`/`eventArraySize`.

**Connection status** (lines 464-486): `status` (ConnStatusType), `asyncStatus`, `xactStatus` (comment: "never changes to ACTIVE"), `last_sqlstate[6]`, `options_valid`, `nonblocking`, `pipelineStatus`, `partialResMode`, `singleRowMode`, `maxChunkSize`, `copy_is_binary`, `copy_already_done`, `notifyHead`/`notifyTail`.

**Multi-host** (lines 482-486): `nconnhost`, `whichhost`, `connhost[]`, `connip`.

**Command queue** (lines 489-499): `cmd_queue_head`, `cmd_queue_tail`, `cmd_queue_recycle` (free-list to cut malloc traffic).

**Socket layer** (lines 501-507): `sock` (`pgsocket`, sentinel `PGINVALID_SOCKET`), `laddr`, `raddr`, `pversion` (FE/BE proto version), `sversion` (e.g. 70401 = 7.4.1), `pversion_negotiated`.

**Auth-exchange state** (lines 510-528): `auth_req_received`, `password_needed`, `gssapi_used`, `sigpipe_so` (SO_NOSIGPIPE), `sigpipe_flag` (MSG_NOSIGNAL), `write_failed`, `write_err_msg`, `auth_required`, `allowed_auth_methods` bitmask, `allowed_sasl_mechs[2]`, `client_finished_auth`, `current_auth_response`.

**Async auth callback** (lines 530-533): `async_auth(conn)`, `cleanup_async_auth(conn)`, `altsock` (alternative FD to poll while external auth runs).

**Transient connect state** (lines 537-552): `target_server_type`, `load_balance_type`, `try_next_addr`, `try_next_host`, `naddr`, `whichaddr`, `addr` (getaddrinfo result), `send_appname`, **`scram_client_key_binary`** + `scram_client_key_len`, **`scram_server_key_binary`** + `scram_server_key_len`, `min_pversion`, `max_pversion`.

**Misc** (lines 555-566): `be_pid` (backend PID, for cancels), `be_cancel_key_len`, `be_cancel_key`, `pstatus` (ParameterStatus linked list), `client_encoding`, `std_strings`, `default_transaction_read_only` (PGTernaryBool), `in_hot_standby`, `verbosity`, `show_context`, `lobjfuncs`, `prng_state`.

**I/O buffers** (lines 568-593): `inBuffer`, `inBufSize`, `inStart`, `inCursor`, `inEnd`; `outBuffer`, `outBufSize`, `outCount`; `outMsgStart`, `outMsgEnd`. **Hard-wired `int` (INT_MAX cap) on buffer sizes** with explicit warning in comment (lines 572-578): changing to `size_t` would require auditing every libpq size calc + `pqCheck{In,Out}BufferSpace`. [verified-by-code, from-comment]

**Row processor workspace** (lines 595-597): `rowBuf`, `rowBufLen`.

**Async result construction** (lines 599-611): `result`, `error_result` (defer ERROR-result construction until end-of-cycle to simplify OOM handling), `saved_result` (preserved tuple metadata in partial-result mode).

**SASL/SSL/GSS** (lines 613-666):
- SASL: `sasl`, `sasl_state`, `scram_sha_256_iterations`.
- Encryption-method tracking: `allowed_enc_methods`/`failed_enc_methods`/`current_enc_method`.
- SSL bools: `ssl_in_use`, `ssl_handshake_started`, `ssl_cert_requested`, `ssl_cert_sent`, `last_read_was_eof`.
- OpenSSL: `ssl` (SSL*), `peer` (X509*), `engine`.
- GSSAPI (ENABLE_GSS): `gctx`, `gtarg_nam`, `gssenc`, `gcred`, plus encrypt/decrypt I/O buffers (`gss_SendBuffer`, `gss_RecvBuffer`, `gss_ResultBuffer` + lengths/cursors), `gss_MaxPktSize`.
- SSPI (Windows): `sspicred`, `sspictx`, `sspitarget`, `usesspi`.

**Error buffers** (lines 686-690): `errorMessage` (`PQExpBufferData`), `errorReported` (cursor: how much of errorMessage has been pushed into a PGresult already; lets a single query cycle accumulate multiple errors without duplicating text), `workBuffer` (scratch).

[verified-by-code throughout]

## Macros

- `pqClearConnErrorState(conn)` (lines 931-933) — reset both `errorMessage` and `errorReported`.
- `pgHavePendingResult(conn)` (lines 940-941) — `result != NULL || error_result`.
- `pqIsnonblocking(conn)` (line 947) — inline form for hot paths.
- `OUTBUFFER_THRESHOLD` = 65536 (line 952) — pipeline-mode auto-flush trigger.
- `SOCK_ERRNO` / `SOCK_STRERROR` / `SOCK_ERRNO_SET(e)` (lines 975-983) — Windows shim: `WSAGetLastError`/`winsock_strerror`/`WSASetLastError` vs `errno`/`strerror_r`/assignment.
- `pglock_thread()`/`pgunlock_thread()` (lines 748-749) — call the registered `pg_g_threadlock` callback.

## Internal function categories

- `fe-connect.c` (727-744): `pqDropConnection`, `pqConnectOptions2`, `pqSetKeepalivesWin32`, `pqConnectDBStart`/`Complete`, `pqMakeEmptyPGconn`, `pqReleaseConnHosts`, `pqClosePGconn`, `pqPacketSend`, `pqGetHomeDirectory`, `pqCopyPGconn`, `pqParseIntParam`.
- `fe-exec.c` (753-770): `pqSetResultError`, `pqResultAlloc`, `pqResultStrdup`, `pqClearAsyncResult`, `pqSaveErrorResult`, `pqPrepareAsyncResult`, `pqInternalNotice`, `pqSaveMessageField`, `pqSaveParameterStatus`, `pqRowProcessor`, `pqCommandQueueAdvance`, `PQsendQueryContinue` (note capital P — semi-public continuation), `PQnfn`.
- `fe-protocol3.c` (774-789): protocol-version-3 message parsing: `pqBuildStartupPacket3`, `pqParseInput3`, `pqGetErrorNotice3`, `pqBuildErrorMessage3`, `pqGetNegotiateProtocolVersion3`, `pqGetCopyData3`, `pqGetline3`, `pqGetlineAsync3`, `pqEndcopy3`, `pqFunctionCall3`.
- `fe-cancel.c` (793): `PQsendCancelRequest`.
- `fe-misc.c` (802-823): `pqCheckOutBufferSpace`/`InBufferSpace`, `pqParseDone`, `pqGetc/Putc/Gets/Gets_append/Puts/Getnchar/Skipnchar/Putnchar/GetInt/PutInt/PutMsgStart/PutMsgEnd`, `pqReadData`, `pqFlush`, `pqWait`, `pqWaitTimed`, `pqReadReady`, `pqWriteReady`.
- `fe-secure.c` (827-837): `pqsecure_open_client/close/read/write/raw_read/raw_write`, `pq_block_sigpipe`/`pq_reset_sigpipe` (non-Windows).
- SSL (843-899): `pgtls_open_client`/`close`/`read`/`read_pending`/`write`, `pgtls_get_peer_certificate_hash` (for SCRAM channel binding `tls-server-end-point`), `pgtls_verify_peer_name_matches_certificate_guts`.
- GSSAPI (908-915): `pqsecure_open_gss`, `pg_GSS_write`, `pg_GSS_read`.
- `fe-trace.c` (920-924): `pqTraceOutputMessage`, `pqTraceOutputNoTypeByteMessage`, `pqTraceOutputCharResponse`.

## Credential lifetime (Phase D candidates)

PGconn fields holding **secret material**: `pgpass`, `sslpassword`, `scram_client_key`/`scram_server_key` (base64) + their `_binary` counterparts, `oauth_client_secret`, `oauth_token`, plus `connhost[i].password` from the password file.

`pqClosePGconn` / `pqReleaseConnHosts` free these along with the rest of the PGconn — i.e. they live for the full lifetime of the PGconn. There is no explicit memset-before-free wiping in the header; whether `freePGconn` (in fe-connect.c) `explicit_bzero`s them is a question for the implementation files.

[ISSUE-libpq-int-001 — maybe] No documented clearance discipline for credential fields. After auth completes, `pgpass`/`sslpassword`/`scram_*_key`/`oauth_token`/`oauth_client_secret` could in principle be zeroed; check whether `fe-connect.c::freePGconn` and `fe-auth-scram.c` use `explicit_bzero`. Heap dumps + core files of long-lived libpq clients (pgbouncer, postgres_fdw worker) leak these otherwise.

[ISSUE-libpq-int-002 — maybe] `inBuffer`/`outBuffer` are deliberately capped at `INT_MAX` (lines 572-578) — large COPY operations larger than 2GiB-1 in a single message would overflow. Modern protocol allows large messages but libpq's int-typed `inEnd`/`outCount` make this a sharp cliff. Comment names the audit cost but doesn't propose a fix.

[ISSUE-libpq-int-003 — maybe] `PGresult.events` is **copied** from PGconn at result-creation; if the conn's event list grows after a result is created, the result doesn't see the new event. Verify whether `PGEVT_RESULTDESTROY` fires for the original event set or the latest — plugin authors expect symmetry.

[ISSUE-libpq-int-004 — maybe] Internal symbols are named `pq*` (lowercase) but a handful of "internal" routines are spelled `PQ*` (e.g. `PQsendQueryContinue` at line 767, `PQnfn` at line 768, `PQsendCancelRequest` at line 793). They're declared in libpq-int.h but the linker still exports them. Tools that scan the public ABI won't know to exclude them.

## Tally

`[verified-by-code]=15 [from-comment]=4 [maybe]=4`
