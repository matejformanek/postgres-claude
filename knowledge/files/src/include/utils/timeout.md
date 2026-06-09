# `src/include/utils/timeout.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Multiplexer over `SIGALRM` allowing multiple distinct timeout reasons
to coexist [from-comment: lines 4-5]. Each `TimeoutId` has its own
handler; the kernel timer is set to the nearest pending deadline.

## Public API

### Built-in IDs [verified-by-code: lines 23-43]

`STARTUP_PACKET_TIMEOUT`, `DEADLOCK_TIMEOUT`, `LOCK_TIMEOUT`,
`STATEMENT_TIMEOUT`, `STANDBY_DEADLOCK_TIMEOUT`, `STANDBY_TIMEOUT`,
`STANDBY_LOCK_TIMEOUT`, `IDLE_IN_TRANSACTION_SESSION_TIMEOUT`,
`TRANSACTION_TIMEOUT`, `IDLE_SESSION_TIMEOUT`,
`IDLE_STATS_UPDATE_TIMEOUT`, `CLIENT_CONNECTION_CHECK_TIMEOUT`,
`STARTUP_PROGRESS_TIMEOUT`.

User-defined slots: `[USER_TIMEOUT, USER_TIMEOUT + 10)`
[lines 39-42]. Total capacity 10 user reasons.

Ordering: "Note that in case multiple timeouts trigger at the same
time, they are serviced in the order of this enum" [lines 21-22] —
so `DEADLOCK_TIMEOUT` fires before `LOCK_TIMEOUT` etc.

### Handler signature [line 46]

```c
typedef void (*timeout_handler_proc)(void);
```

Runs in signal context-equivalent (actually called from
`ProcessInterrupts` after the signal sets a flag — see PG
deferred-interrupt model).

### Setup / register [lines 76-77]

- `InitializeTimeouts()` — postmaster boot.
- `RegisterTimeout(id, handler)` — install a handler; returns the
  ID (allowing `USER_TIMEOUT + N` allocation).
- `reschedule_timeouts()` — recompute kernel timer after wakeup.

### Operation [lines 81-88]

Single-id: `enable_timeout_after(id, delay_ms)`,
`enable_timeout_every(id, fin_time, delay_ms)`,
`enable_timeout_at(id, fin_time)`, `disable_timeout(id,
keep_indicator)`.

Multi: `enable_timeouts(...)` / `disable_timeouts(...)` with
`EnableTimeoutParams[]` / `DisableTimeoutParams[]`.

`disable_all_timeouts(keep_indicators)` is the
end-of-transaction reset.

### Accessors [lines 91-94]

`get_timeout_active`, `get_timeout_indicator(id, reset)`,
`get_timeout_start_time`, `get_timeout_finish_time`.

## Invariants

- **INV-DEFERRED** [inferred] Handlers run from CHECK_FOR_INTERRUPTS,
  not from signal context — signal merely sets a pending flag.
  Callbacks may therefore `ereport(ERROR, ...)` safely.
- **INV-SERVICE-ORDER** [verified-by-code: lines 21-22] If two
  timeouts expire in the same tick, lower-enum-value fires first.
  Adding a new built-in changes ordering — be careful.
- **INV-USER-SLOTS** [verified-by-code: lines 39-42] Max 10
  user-defined timeouts cluster-wide. Re-registering at the same ID
  replaces.
- **INV-INDICATOR** [verified-by-code: line 73, 92] Each timeout
  has a sticky "fired" indicator readable via
  `get_timeout_indicator`; `disable_timeout(id, keep_indicator)`
  decides whether to clear it on disable.

## Trust boundary

- Handlers run with backend privilege. A loaded extension that
  registers a `USER_TIMEOUT + N` handler can take action on every
  fire. Hardening posture: same as any module hook.
- `CLIENT_CONNECTION_CHECK_TIMEOUT` is exposed via GUC; reducing it
  to 0 disables the check — DoS detection only.

## Cross-refs

- `tcop/postgres.c` — backend's main loop installs the standard
  handlers.
- `storage/proc.c` — DEADLOCK_TIMEOUT for the lock manager.
- `storage/lmgr.c` — LOCK_TIMEOUT.

## Issues

- [ISSUE-API: only 10 USER_TIMEOUT slots; not documented as a hard
  cluster-wide limit at the header (low)] — lines 39-42.
- [ISSUE-DOC: handlers' actual execution context (deferred via
  CFI vs signal-context) isn't named in the header — easy to write
  an unsafe handler if you only read this file (medium)] —
  line 46.
