# tidpath.c — TidPath / TidRangePath generation

- **Source:** `source/src/backend/optimizer/path/tidpath.c` (604 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

Detect `WHERE CTID = pseudoconstant`, `CTID = ANY(array)`, OR-of-CTIDs,
and `CTID < / > const` clauses, generating direct heap-fetch paths
(TidPath) or sequential range scans (TidRangePath). Also handles
`WHERE CURRENT OF cursor` via CurrentOfExpr. [from-comment:5-26]

## 2. Mental model

"Pseudoconstant" here means: no volatile function, no Var of the
relation under consideration. Vars of *other* rels are fine, making
parameterized TID scans possible. [from-comment:14-17]

## 3. Public entry

`bool create_tidscan_paths(PlannerInfo *root, RelOptInfo *rel)` at
line ~496. [verified-by-code]

Called by `allpaths.c:set_plain_rel_pathlist` for each heap baserel
before bitmap/index path generation.

## 4. Notable

- `CurrentOfExpr` is kept as a distinct node all the way to execution
  rather than translated to a CTID comparison — more practical given
  the runtime ITP lookup. [from-comment:20-24]
- Multiple OR'd CTID equalities become a single TidPath with an array of
  TIDs (executor in `nodeTidscan.c`).

## 5. Tags
`[verified-by-code]` ×1, `[from-comment]` ×4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
