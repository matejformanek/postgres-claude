# src/include/tcop/backend_startup.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 122 [verified-by-code]

## Role

Front-end of the per-connection backend lifecycle. Postmaster forks
a child, passes a `BackendStartupData` blob, and the child runs
`BackendMain`. This header defines that blob plus the
`log_connections` granular logging machinery.

## Public API

- GUCs: `Trace_connection_negotiation`, `log_connections`,
  `log_connections_string` (`:20-22`).
- Global: `conn_timing` (extern struct ConnectionTiming) (`:25`).
- `CAC_state` enum: OK / STARTUP / SHUTDOWN / RECOVERY /
  NOTHOTSTANDBY / TOOMANY (`:33-41`) — postmaster's accept-or-
  reject decision passed to backend.
- `BackendStartupData` — `CAC_state canAcceptConnections`,
  `socket_created`, `fork_started` (`:44-60`).
- `LogConnectionOption` bitmask enum (`:74-89`) — RECEIPT,
  AUTHENTICATION, AUTHORIZATION, SETUP_DURATIONS, plus
  convenience aliases `ON` (legacy <= PG17) and `ALL`.
- `ConnectionTiming` — fine-grained timestamps for connection
  setup phases (socket_create / fork_start / fork_end /
  auth_start / auth_end / ready_for_use) (`:97-118`).
- `BackendMain(startup_data, startup_data_len)` —
  `pg_noreturn` entry (`:120`).

## Invariants

- INV-STARTUPDATA-EXACT: `BackendMain` is called with
  `startup_data_len == sizeof(BackendStartupData)`; ABI change
  requires a postmaster rebuild matching the backend.
- INV-CAC-FIRST-MSG: if `canAcceptConnections != CAC_OK`,
  backend sends the corresponding error to client and exits.
  Each CAC_* maps to a fixed SQLSTATE-ish error.
- INV-LOG-CONNECTIONS-PARSE: `log_connections` (uint32 bitmask)
  is computed from `log_connections_string` via a check_hook
  (PG18 made it granular; pre-18 was bool).
- INV-CONN-TIMING-MONOTONIC: timestamps in `ConnectionTiming`
  are taken from `GetCurrentTimestamp` and naturally
  monotonic within a connection (no NTP step backward expected
  inside fork-to-ready window).

## Notable internals

- `socket_created` is taken in postmaster BEFORE fork; passed
  to backend so it can compute "fork latency" as
  `fork_started - socket_created`.
- `LOG_CONNECTION_ON` (`:80-83`) explicitly preserves PG <= 17
  behavior: receipt + auth + authorization.
- `conn_timing` is filled progressively by the backend; emitted
  via `log_connections SETUP_DURATIONS`.

## Trust boundary / Phase D surface

- **A2 echo — libpq protocol surface.** `BackendMain` is the
  function that runs the StartupPacket handshake. Top
  surface:
  - StartupPacket parsing happens AFTER `BackendMain` is
    entered (not in postmaster) — historically a defense:
    a malformed packet only crashes the per-connection
    backend.
  - SSL/GSS negotiation (controlled by
    `Trace_connection_negotiation` GUC for verbose logging)
    must complete before authentication; bugs here have
    been CVE vectors (CVE-2024-10977 SSL identity confusion,
    etc.).
  - `log_connections SETUP_DURATIONS` exposes timing
    side-channel: a slow auth-end vs auth-start can leak
    whether a user exists (different password-hash lookup
    paths). Mitigation depends on auth method.
- **CAC_NOTHOTSTANDBY** path: backend tells client "this is
  a standby and you don't have hot_standby". An attacker
  fingerprinting the cluster can distinguish primary vs
  standby pre-auth. Standard, by design.
- **CAC_TOOMANY** path: leaks the existence of the postmaster
  config to pre-auth clients (max_connections hit). Standard.
- **`startup_data` reused across fork.** On Windows (no fork),
  this is the cross-process handoff format — corruption of
  the in-flight handoff is a low-prob escalation.

## Cross-references

- `tcop/tcopprot.h` — defines `PostgresMain` called by
  `BackendMain` after startup.
- `libpq/auth.h` — `ClientAuthentication`.
- `libpq/libpq-be.h` — `Port` struct (`MyProcPort`).
- `postmaster/postmaster.h` — backend fork path.
- A2 phase-D notes on libpq protocol surface.

## Issues / drift

- `[ISSUE-TRUST: A2 echo — log_connections SETUP_DURATIONS publishes per-phase auth timing; user-existence timing side-channel; not flagged in header (medium)] — source/src/include/tcop/backend_startup.h:74-118`
- `[ISSUE-DOC: CAC_* enum order is wire-significant (each maps to a fixed error); changing order would be ABI break, not commented (low)] — source/src/include/tcop/backend_startup.h:33-41`
- `[ISSUE-CODE: BackendStartupData uses two TimestampTz fields conditionally ("only used for client and wal sender connections") — unused for autovacuum / bgworker but always allocated (low)] — source/src/include/tcop/backend_startup.h:48-60`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
