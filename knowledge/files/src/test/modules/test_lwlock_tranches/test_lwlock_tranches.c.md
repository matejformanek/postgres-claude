---
path: src/test/modules/test_lwlock_tranches/test_lwlock_tranches.c
anchor_sha: e18b0cb7344
loc: 141
depth: read
---

# src/test/modules/test_lwlock_tranches/test_lwlock_tranches.c

## Purpose

Smoke-tests the LWLock tranche API that extensions use to allocate their own
named LWLocks. Covers both flavors: the early-startup
`RequestNamedLWLockTranche` path (one allocation request per name, locks live
in MainLWLockArray) and the runtime `LWLockNewTrancheId` +
`GetNamedLWLockTranche` path. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `test_lwlock_tranches.c:27` | Hooks `shmem_request_hook` to call `RequestNamedLWLockTranche` twice |
| `test_startup_lwlocks` | `:51` | Acquires/releases the requested tranches and checks `GetLWLockIdentifier` returns the right name |
| `test_lwlock_tranche_create` | `:87` | Thin wrapper over `LWLockNewTrancheId` |
| `test_lwlock_tranche_lookup` | `:102` | Thin wrapper over `GetNamedLWLockTranche` |
| `test_lwlock_get_lwlock_identifier` | `:113` | Thin wrapper over `GetLWLockIdentifier(PG_WAIT_LWLOCK, eventId)` |
| `test_lwlock_initialize` | `:131` | Thin wrapper over `LWLockInitialize` on a stack-allocated `LWLock` |

## Internal landmarks

- The `shmem_request_hook` chain is preserved (`prev_shmem_request_hook`,
  `:24, :30, :37`) — the canonical "good citizen" pattern for hook layering.
- Two tranches are requested: a single lock ("...startup", `:44`) and a
  10-lock array ("...startup10", `:45`). Both must be requested at
  `shared_preload_libraries` time; trying to call `RequestNamedLWLockTranche`
  later would error.

## Invariants & gotchas

- **Must be in `shared_preload_libraries`.** `RequestNamedLWLockTranche` only
  works during postmaster startup; the test exercises this constraint.
- `test_lwlock_initialize` initializes a `LWLock` on the C stack — fine for
  the test, but in real code an LWLock must live in shared memory or you'll
  get torn reads under contention.
- `GetLWLockIdentifier` indexes tranches starting at `LWTRANCHE_FIRST_USER_DEFINED`
  in registration order — the test relies on the order of the two
  `RequestNamedLWLockTranche` calls.

## Cross-refs

- `source/src/backend/storage/lmgr/lwlock.c` — the tranche machinery.
- `source/src/include/storage/lwlock.h` — public API: `RequestNamedLWLockTranche`,
  `GetNamedLWLockTranche`, `LWLockNewTrancheId`, `LWLockInitialize`.
- `knowledge/idioms/locking.md` — once written, this is the worked example.
