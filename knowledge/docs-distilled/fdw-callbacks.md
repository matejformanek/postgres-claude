---
source_url: https://www.postgresql.org/docs/current/fdw-callbacks.html
chapter: "58.2 Foreign Data Wrapper Callback Routines"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# FDW callback routines (`FdwRoutine`) — §58.2

Distilled from §58.2. The parent `fdwhandler.html`
(→ `fdwhandler.md`) frames the FDW; this leaf is the exhaustive callback
catalog. The `FdwRoutine` struct is declared in
`src/include/foreign/fdwapi.h`. **Only the seven scan callbacks are
required; everything else is optional and feature-gated.**

## Non-obvious claims

- **Required set (basic scan):** `GetForeignRelSize`, `GetForeignPaths`,
  `GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`,
  `ReScanForeignScan`, `EndForeignScan`. Everything below is optional;
  a NULL pointer means "feature unsupported" and the relevant operation
  errors out (or silently degrades). [from-docs §58.2]
- The plan/exec split is strict: `BeginForeignScan` must NOT start the
  actual scan — the first `IterateForeignScan` does. And
  `IterateForeignScan` runs in a **short-lived memory context that is
  reset between calls**, so anything that must persist across rows has to
  live in a context created in `BeginForeignScan`. [from-docs §58.2.1]
- `(eflags & EXEC_FLAG_EXPLAIN_ONLY)` is the recurring guard: in
  `BeginForeignScan` / `BeginForeignModify` / `BeginDirectModify`, when
  set, do only the minimum needed for the matching Explain*/End* call —
  don't open connections. [from-docs §58.2]
- **Row-count correctness depends on returning a slot.** `ExecForeignInsert/
  Update/Delete` must return *some* non-NULL slot (even the input slot
  reused) to signal success; returning NULL means "row not affected" and
  undercounts. [from-docs §58.2.4]
- `ExecForeignUpdate`'s `planSlot` only holds **changed** columns plus
  the junk row-identity columns from `AddForeignUpdateTargets` — you
  **cannot** index into it by foreign-table attribute number. Row
  identity travels as junk columns (`ctid`, `wholerow`, `tableoid`,
  …), declared via `add_row_identity_var`. [from-docs §58.2.4]
- **Direct modify** (`PlanDirectModify` → `Begin/Iterate/EndDirectModify`)
  is the "push the whole UPDATE/DELETE to the remote" optimization. It's
  only safe when there are no row-level local triggers, no stored
  generated columns, and no parent-view `WITH CHECK OPTION`. When
  `IterateDirectModify` runs without RETURNING it must **increment the
  row count itself**. [from-docs §58.2.4]
- **Join pushdown** (`GetForeignJoinPaths`) differs from base-rel paths:
  it is invoked *repeatedly* for different inner/outer combos, is not
  required to produce any path, and the chosen `ForeignPath` must set
  `scanrelid = 0` and fully populate `fdw_scan_tlist` (no catalog row
  type to fall back on). PG16+ splits `fs_relids` (includes outer-join
  RT indexes) from `fs_base_relids` (base rels only). [from-docs §58.2.2]
- **Outer-join pushdown breaks the cheap recheck path.** For READ
  COMMITTED correctness you normally set `fdw_recheck_quals`; but once an
  outer join is pushed down, a failing qual must NULL-extend fields
  rather than drop the row, so you must implement `RecheckForeignScan`
  (typically building a local nested-loop alternative via
  `GetExistingLocalJoinPath`). [from-docs §58.2.6]
- **Late row locking:** `GetForeignRowMarkType` returning non-`ROW_MARK_COPY`
  is what makes `RefetchForeignRow` get called. `rowid` is typed `Datum`
  but currently only a `tid` is allowed. Must respect `SKIP LOCKED` via
  `erm->waitPolicy` instead of erroring. [from-docs §58.2.6]
- **Batch insert** (`ExecForeignBatchInsert` + `GetForeignModifyBatchSize`)
  is mutually-required: if either is NULL, the executor falls back to
  per-row `ExecForeignInsert`. Batch path is disabled when a RETURNING
  clause is present (only WITH CHECK OPTION / AFTER ROW triggers use it).
  [from-docs §58.2.4]
- **Parallel** and **async** are all-or-nothing groups: parallel needs
  the DSM estimate/init/worker trio (DSM chunks must be pointer-free),
  async needs `IsForeignPathAsyncCapable` + `ForeignAsyncRequest` +
  `ForeignAsyncConfigureWait` + `ForeignAsyncNotify` (the latter two
  wire an fd into the parent Append's event set —
  cf. `execAsync.c`). [from-docs §58.2.10–11]
- `ImportForeignSchema` returns a List of `CREATE FOREIGN TABLE` **C
  strings** that core parses/executes; the FDW need not honor the
  LIMIT TO / EXCEPT filter (core re-filters) but can use
  `IsImportableForeignTable()` to skip work early. [from-docs §58.2.9]

## Links into corpus

- Parent chapter: [[knowledge/docs-distilled/fdwhandler.md]].
- Planning-side companion (this run): [[knowledge/docs-distilled/fdw-planning.md]].
- Source struct: [[knowledge/files/src/include/foreign/fdwapi.h.md]]
  (`FdwRoutine` — the pointer-table this chapter narrates).
- Custom-scan analogue (the other planner-pluggable provider):
  [[knowledge/docs-distilled/custom-scan.md]].
- Executor wiring for ForeignScan lives alongside
  [[knowledge/subsystems/optimizer.md]] (path → plan).

## Caveats / verification

- All claims `[from-docs §58.2]`. The PG16+ `fs_relids` /
  `fs_base_relids` split and exact callback signatures should be
  re-verified against `source/src/include/foreign/fdwapi.h` and
  `nodes/plannodes.h` (ForeignScan) at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735` before citing line numbers.
