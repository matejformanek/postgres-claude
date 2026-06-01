# nodeResult.c

- **Source:** `source/src/backend/executor/nodeResult.c` (≈220 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Three distinct uses:

1. **No-input projection** — `SELECT 1+1` or `INSERT INTO t VALUES (1)`:
   no scan, just emit one row of computed values.
2. **One-Time Filter optimization** — when the qual depends on no input
   columns (e.g. `WHERE current_user = 'foo'`), evaluate it once: if
   false, return no rows; if true, return outerPlan's rows verbatim.
   EXPLAIN labels this "One-Time Filter".
3. **Modify-table input pipeline** — INSERT/UPDATE/COPY/MERGE often have
   a Result above a row source to compute defaults / generated columns.

[from-comment] `:17-37`

## Mechanics

- Init: evaluate the optional `resconstantqual` once (the one-time qual).
  If false, set a flag so all subsequent ExecResult calls return NULL.
- Per call: if outerPlan is NULL (computed-only), emit one row via
  ExecProject, then EOS. Else pass through outerPlan, projecting.

## Tags

- [verified-by-code] resconstantqual one-time eval flow.
- [from-comment] file head describing the three use cases.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
