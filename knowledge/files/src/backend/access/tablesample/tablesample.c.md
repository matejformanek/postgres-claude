# tablesample.c

- **Source path:** `source/src/backend/access/tablesample/tablesample.c`
- **Lines:** 40
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tsmapi.h`, `system.c`, `bernoulli.c`, `executor/nodeSamplescan.c` (consumer).

## Purpose

One function: `GetTsmRoutine(tsmhandler)`. Calls the tablesample method's handler function and validates that it returned a `TsmRoutine *`. Analogous to `tableamapi.c::GetTableAmRoutine` but for `TABLESAMPLE` methods. [from-comment, tablesample.c:1-13]

## Top-of-file comment

> "Support functions for TABLESAMPLE feature" [from-comment, tablesample.c:1-12]

## Public surface

- `GetTsmRoutine` (27) — `OidFunctionCall1(tsmhandler, NULL)`. If the result isn't a `TsmRoutine` node, `elog(ERROR, "tablesample handler function %u did not return a TsmRoutine struct", tsmhandler)`. Returns the struct so the caller can dispatch.

## Key invariants

- The handler is called with a single null argument (handlers ignore it); this odd signature is historical.
- TsmRoutines, unlike IndexAmRoutine / TableAmRoutine, are NOT checked field-by-field here. Validation of individual callbacks happens at use sites in `nodeSamplescan.c` and the planner.

## Cross-references

- Called from `optimizer/util/plancat.c` and `executor/nodeSamplescan.c` when setting up a TABLESAMPLE scan.
- In-tree implementations: `system.c` (block-sampling, repeatable across queries) and `bernoulli.c` (per-tuple Bernoulli trial).

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=1 [from-readme]=0 [inferred]=0 [unverified]=0`
