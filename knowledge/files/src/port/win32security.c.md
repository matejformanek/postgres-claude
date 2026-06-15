---
path: src/port/win32security.c
anchor_sha: e18b0cb7344
loc: 190
depth: read
---

# src/port/win32security.c

## Purpose

Two Windows-only security predicates used by PG startup:
`pgwin32_is_admin()` and `pgwin32_is_service()`. Both probe the
current process token via Win32 SID/`CheckTokenMembership` machinery.
`[verified-by-code]`

- `is_admin` — Returns nonzero when the user is in
  `Administrators` or `Power Users`. PG refuses to run as
  administrator (it would be a privilege violation parallel to running
  as root on Unix), so the postmaster startup path checks this and
  aborts.
- `is_service` — Detects whether PG was launched by the Windows
  Service Control Manager. Affects logging behavior (where stderr
  goes) and pg_ctl's interaction model.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pgwin32_is_admin(void)` | `win32security.c:49` | 1 = admin/power-user, 0 = not, `exit(1)` on Win32 API failure |
| `int pgwin32_is_service(void)` | `win32security.c:120` | 1 = service, 0 = not, -1 = error; cached via `static int _is_service` |

## Internal landmarks

- `log_error` helper (`win32security.c:27-39`) — variadic stderr
  writer. Uses `vwrite_stderr` in backend, `vfprintf(stderr,...)` in
  frontend. Needed because **this code runs too early in startup to
  use `ereport`** (`:46-47`).
- `pgwin32_is_admin` (`:49-92`):
  1. `AllocateAndInitializeSid` for the Administrators well-known SID
     (`SECURITY_BUILTIN_DOMAIN_RID` + `DOMAIN_ALIAS_RID_ADMINS`).
  2. Same for Power Users.
  3. `CheckTokenMembership(NULL, sid, &result)` for each.
  4. `FreeSid` on both.
  5. Return 1 if either is true.
- `pgwin32_is_service` (`:120-190`) — the three-prong test from the
  header comment (`:96-107`):
  1. **stderr handle invalidity** (`:134-139`): services don't get a
     real stderr; if `GetStdHandle(STD_ERROR_HANDLE)` returns
     `INVALID_HANDLE_VALUE` or `NULL`, we're a service. If it's
     valid, immediately conclude "not a service" (early return at
     `:137-138`).
  2. **LocalSystem membership** (`:141-163`): allocate
     `SECURITY_LOCAL_SYSTEM_RID` SID and `CheckTokenMembership`.
     Services running as LocalSystem need this explicit check
     because LocalSystem tokens do NOT contain
     `SECURITY_SERVICE_RID` (a documented surprise).
  3. **`SECURITY_SERVICE_RID` membership** (`:165-188`): the normal
     services-run-by-SCM path.
- Result cached in `static int _is_service` (`:122`); first call
  computes, subsequent calls return cached value (`:130-131`).

## Invariants & gotchas

- **`is_admin` calls `exit(1)` on Win32 SID-allocation failure**
  (`win32security.c:64`, `:74`, `:82`). Used early in startup where
  there's no graceful error path, and a SID-allocation failure
  indicates a deeply broken system.
- **`is_service` returns -1 on error, not `exit`** — different
  contract from `is_admin`. Callers (`postmaster.c`, `pg_ctl`) must
  check the three-way return value.
- The cache (`static int _is_service`) means **a subprocess that
  inherits PG state via `fork`-emulation could see a stale value**.
  Win32 backends are normally spawned via `CreateProcess` from a fresh
  state, so this isn't an issue in practice, but it's a footgun for
  any future shared-state model.
- The "stderr is not valid" check (`:134-139`) is the cheapest and
  fastest of the three — most non-service processes return on that
  branch and skip the SID allocations entirely.
- `_(...)` (gettext) is used for `is_admin` error messages
  (`:62,72,80`) but **not** for `is_service` error messages
  (`:146,152,170,177`) — historical inconsistency. `[verified-by-code]`

## Cross-refs

- `source/src/backend/main/main.c` — startup-time check for
  `pgwin32_is_admin` to refuse running as administrator.
- `source/src/bin/pg_ctl/pg_ctl.c` — uses `pgwin32_is_service` to
  decide between interactive and service mode.
