# Issues — `src/include/foreign/`

Per-subdirectory issue register for the FDW interface: `fdwapi.h`
(callback contract) and `foreign.h` (data-wrapper / server /
user-mapping / table records).

**Parent docs:** `knowledge/files/src/include/foreign/{fdwapi,foreign}.h.md`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/foreign/fdwapi.h:208-286 | undocumented-invariant | likely | `FdwRoutine` ABI stability is convention-only — no version field, reorder = silent miscall | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/fdwapi.h:46-49 | undocumented-invariant | likely | Slot ownership returned by `IterateForeignScan`/`Exec(I/U/D)` not stated in header — convention is FDW-owns-slot | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/fdwapi.h:183-185 | undocumented-invariant | likely | `IsForeignScanParallelSafe` contract is honor-system; backend-local FDs in a "safe" FDW corrupt parallel scans | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/fdwapi.h:190-196 | doc-drift | maybe | Async callback ordering (Request → ConfigureWait → Notify) only documented by example in postgres_fdw | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/fdwapi.h:167-169 | question | nit | `ExecForeignTruncate` atomicity contract (partial truncate legal?) not stated | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/fdwapi.h:151-154 | question | maybe | `AcquireSampleRowsFunc` memory-context scoping — FDW pallocs into CurrentMemoryContext leak past ANALYZE | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/fdwapi.h:294 | doc-drift | nit | `GetFdwRoutineForRelation(makecopy)` flag rationale not in header | open | files/.../fdwapi.h.md |
| 2026-06-11 | src/include/foreign/foreign.h:40-42 | doc-drift | nit | `ForeignServer.servertype`/`serverversion` NULL signaling (NULL pointer vs empty string) not stated | open | files/.../foreign.h.md |
| 2026-06-11 | src/include/foreign/foreign.h:32-43,57 | undocumented-invariant | likely | `options` DefElem lists are cache-owned; treat as immutable, not stated | open | files/.../foreign.h.md |
| 2026-06-11 | src/include/foreign/foreign.h:68 | doc-drift | nit | `GetForeignServer` (non-Extended) error-vs-NULL contract not in header | open | files/.../foreign.h.md |

## Wontfix / Submitted / Landed

(empty)

## Notes

- **Phase-D angle**: `fdwapi.h` is THE largest trust-boundary header
  in core PG by raw callback count (~40 typedefs). Every entry
  there crosses from PG core into FDW-author code. The
  highest-leverage Phase-D contributions in this subdir would be:
  1. Document the slot-ownership contract in-header (currently
     learned by reading postgres_fdw).
  2. Add a version field to `FdwRoutine` so ABI breaks are
     detectable rather than silent (probably requires upstream
     buy-in via `pgsql-hackers`).
  3. Tighten parallel-safety: today an FDW can declare itself
     safe with no compile-time check; an Assert in DSM-init that
     touches typical backend-local state (`MyDatabaseId` per-fork
     etc.) would catch some footguns.
  4. Document the async-callback ordering in-header rather than
     by-example.
- `foreign.h` is much smaller — the only material concerns are
  the immutability of cached `options` lists and the asymmetric
  missing_ok contract across the Extended/non-Extended pairs.
