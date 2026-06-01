# backend_startup.c

- **Source:** `source/src/backend/tcop/backend_startup.c` (1157 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (BackendMain + BackendInitialize)

## Purpose

The post-fork entry point for `B_BACKEND` / `B_DEAD_END_BACKEND` /
`B_WAL_SENDER` (before the latter type-switch). Runs everything between
"postmaster gave me a socket" and "PostgresMain takes over": SSL/GSS
negotiation, startup-packet decode, HBA-driven authentication, PGPROC
allocation. [from-comment] `:3-12`

## Lifecycle position

- `main_fn = BackendMain` for `B_BACKEND` and `B_DEAD_END_BACKEND` per
  `proctypelist.h:37, 43`.
- Called from `launch_backend.c::postmaster_child_launch` via the dispatch
  table.

## `BackendMain` (`:76-125`)

1. Validate `startup_data_len == sizeof(BackendStartupData)`. `:80`
2. `#ifdef EXEC_BACKEND` + `USE_SSL`: re-initialize SSL because the SSL
   library state can't ride through fork+exec. `:97-106`
3. `BackendInitialize(MyClientSocket, bsdata->canAcceptConnections)` — read
   startup packet, auth.
4. **`InitProcess()`** — allocate a `PGPROC` in shmem. *Must* happen before
   any LWLock / shmem access. `:113-116`
5. Switch out of `PostmasterContext` (kept alive for HBA data until
   `InitPostgres` deletes it).
6. `PostgresMain(database_name, user_name)`. Never returns.

## `BackendInitialize` (`:141+`)

Critical invariant from the comment block (`:128-139`):

> Note: this code does not depend on having any access to shared memory.
> Indeed, our approach to SIGTERM/timeout handling **requires** that shared
> memory not have been touched yet.

That's why `InitProcess` is deferred to *after* `BackendInitialize` returns.
Within `BackendInitialize`, `process_startup_packet_die` is the SIGTERM
handler; it does `_exit(1)` because there is **nothing in shmem to clean up
yet**. If postmaster needs FAST/IMMEDIATE shutdown while a client is hung
sending a startup packet, this is what protects us.

Sequence:

1. `ReserveExternalFD()` for the client socket. `:152`
2. Optional `PreAuthDelay` for debugger attach. `:161`
3. Set `ClientAuthInProgress = true` (limits log message visibility).
4. `pq_init(client_sock)` in `TopMemoryContext`; sets `MyProcPort`. `:177`
5. `whereToSendOutput = DestRemote` — now ereport can talk to the client.
6. Install pre-auth signal handlers + `InitializeTimeouts()` + apply
   `StartupBlockSig`. `:196-199`
7. Resolve `remote_host` / `remote_port` via `pg_getnameinfo_all`.
8. `ProcessSSLStartup` (`:401`) — handle SSLRequest / GSSAPI.
9. `ProcessStartupPacket` (`:486`) — read params, set `MyProcPort->database_name`,
   `user_name`, GUC overrides; check protocol version.
10. Either run authentication via `ClientAuthentication()` (called later
    inside `InitPostgres` since HBA matching needs DB) or, for special
    requests, handle them and `proc_exit(0)`:
    - **Cancel request** → `ProcessCancelRequestPacket` (`:917`).
    - **Negotiate version** → `SendNegotiateProtocolVersion` (`:959`).

## Cancel-request protocol

`ProcessCancelRequestPacket` (`:917`) decodes pid + 32/64-bit cancel key,
calls `SendCancelRequest(pid, key)` (in `storage/ipc/procsignal.c`), then
exits — this whole exchange is handled by a `B_DEAD_END_BACKEND` so the
target backend's main process never sees the cancel-channel socket.

## GUCs / globals

- `Trace_connection_negotiation` — debug toggle.
- `log_connections` (uint32 bitmask), `log_connections_string` (the GUC
  string). `validate_log_connections_options` / `check_log_connections` /
  `assign_log_connections` (`:1018, :1110, :1154`) — parser + GUC hooks.
- `conn_timing` — `ConnectionTiming` struct of timestamps for the
  `log_connections=duration` feature.

## Headers

- `tcop/backend_startup.h` — `BackendStartupData`, `ConnectionTiming`,
  `BackendMain`, `BackendInitialize` prototypes (some via tcopprot.h).
