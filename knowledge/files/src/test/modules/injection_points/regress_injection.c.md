# src/test/modules/injection_points/regress_injection.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 78
**Verification depth:** full read

## Role

A companion C file in the `injection_points` module that holds "test-specific subject matter" — SQL-callable helpers that particular isolation/regression specs need, but which aren't part of the generic injection-point harness. At this pin it contains exactly one function, `removable_cutoff`, a thin wrapper around `GetOldestNonRemovableTransactionId()` written for the `syscache-update-pruned.spec` isolation test. [verified-by-code] `source/src/test/modules/injection_points/regress_injection.c:3` (header comment), `:25` (function comment).

## Public API

- `removable_cutoff(rel_oid)` — `PG_FUNCTION_INFO_V1`, returns a `FullTransactionId`. Computes the oldest non-removable XID for the given relation (or globally if arg is NULL), epoch-corrected. [verified-by-code] `source/src/test/modules/injection_points/regress_injection.c:40`

## Invariants

- INV-1: To avoid ascribing the returned `xid` to the wrong epoch, the function retries `GetOldestNonRemovableTransactionId` in a loop until `ReadNextFullTransactionId()` is stable across the call (i.e. `nextXid` didn't advance during the computation). The loop body runs `CHECK_FOR_INTERRUPTS()`. [verified-by-code] `source/src/test/modules/injection_points/regress_injection.c:64`
- INV-2: The relation, if opened, is opened with `AccessShareLock` and closed with the same lock level; a NULL arg means no relation is opened (global horizon). [verified-by-code] `source/src/test/modules/injection_points/regress_injection.c:50`, `:73`
- INV-3: The result is built via `FullTransactionIdFromAllowableAt(next_fxid, xid)` — the stable `next_fxid` supplies the epoch for the bare `xid`. [verified-by-code] `source/src/test/modules/injection_points/regress_injection.c:76`

## Notable internals

- Backward-movement caveat: the header comment explains the cutoff can move backward in general; the test relies on `runningcheck=false` plus passing a shared catalog to keep it monotone. A guard warns at `WARNING` level when called on a non-shared rel while `autovacuum_start_daemon` is on. [verified-by-code] `source/src/test/modules/injection_points/regress_injection.c:25`, `:53`
- Despite the filename, this file contains no injection-point calls at this pin — it's a grab-bag for regression-support C that ships in the same module. [inferred] `source/src/test/modules/injection_points/regress_injection.c:1`

## Cross-refs

- `source/src/backend/storage/ipc/procarray.c` — `GetOldestNonRemovableTransactionId`, `ComputeXidHorizons` (referenced by name in the comment).
- `source/src/backend/access/transam/transam.c` / `varsup.c` — `ReadNextFullTransactionId`, `FullTransactionIdFromAllowableAt`.
- `injection_points.c` (same module) — the generic harness this file is built alongside.

## Potential issues

None.
