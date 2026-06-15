---
path: src/test/modules/injection_points/regress_injection.c
anchor_sha: e18b0cb7344
loc: 78
depth: read
---

# src/test/modules/injection_points/regress_injection.c

## Purpose

Supplementary SQL-callable function(s) layered on the `injection_points`
test module to support specific isolation tests. Currently a single
function: `removable_cutoff(regclass)` — a wrapper around
`GetOldestNonRemovableTransactionId()` that returns a `FullTransactionId`
stable against `next_fxid` advancement during the call.
`[verified-by-code]` `regress_injection.c:40-78`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `removable_cutoff(regclass)` | `:42` | Wrapper around `GetOldestNonRemovableTransactionId`; retries until `next_fxid` is stable so the returned XID's epoch is unambiguous |

## Internal landmarks

- `:53-55` — warns if called on a non-shared relation while
  `autovacuum_start_daemon` is on, because the cutoff can move backward
  under concurrent autovacuum `[from-comment]` `:30-39`.
- Retry loop (`:64-71`) reads `next_fxid`, calls
  `GetOldestNonRemovableTransactionId`, re-reads `next_fxid`, and loops
  while they differ — bounded by the rate of XID allocation.
- `FullTransactionIdFromAllowableAt` (`:76`) is the official "promote a
  32-bit XID to FullTransactionId" using the known nextXid epoch.

## Invariants & gotchas

- TEST MODULE — used by the `syscache-update-pruned.spec` isolation test.
  Never load in production: SQL-callable helpers that prod XID horizons
  are not appropriate for live systems.
- Calling on a non-shared relation under autovacuum yields a WARNING but
  not an error; the test author is expected to disable autovacuum
  externally for stable results.
- `CHECK_FOR_INTERRUPTS()` inside the retry loop (`:67`) ensures the
  function can be cancelled if the system is under heavy XID churn.

## Cross-refs

- `knowledge/files/src/test/modules/injection_points/injection_points.c.md`
  — the main injection-point module this rides alongside.
- `source/src/backend/storage/ipc/procarray.c` —
  `GetOldestNonRemovableTransactionId` definition.
- `source/src/backend/access/transam/transam.c` —
  `FullTransactionIdFromAllowableAt`.
