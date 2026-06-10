# `src/include/access/tsmapi.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**83 lines.**

## Role

Public API for **TABLESAMPLE** methods. Defines `TsmRoutine` — the
struct a tablesample handler function returns, populated with planner
+ executor callbacks. The two built-in methods (`SYSTEM`, `BERNOULLI`)
plus the contrib extensions `tsm_system_rows` and `tsm_system_time`
all implement this API.
[verified-by-code] `source/src/include/access/tsmapi.h:1-11`

## Public API

Six callback typedefs (lines 23-44):
- `SampleScanGetSampleSize` — planner: estimate (pages, tuples).
- `InitSampleScan` — executor init (optional, can be NULL).
- `BeginSampleScan` — start with `(params, nparams, seed)`.
- `NextSampleBlock` — pick next block, or `InvalidBlockNumber` for "all".
- `NextSampleTuple` — pick next offset within block.
- `EndSampleScan` — cleanup (optional).

`TsmRoutine` struct (lines 56-76):
- `type` (NodeTag) — for `IsA()` checks.
- `parameterTypes` — `List *` of arg type OIDs (drives parse-time
  type checking of TABLESAMPLE arguments).
- `repeatable_across_queries`, `repeatable_across_scans` — control
  whether REPEATABLE clause is allowed and how rescans behave.
- Six function pointers (subset can be NULL).

One extern: `GetTsmRoutine(tsmhandler)` — fmgr-call the handler
function and unpack the returned `TsmRoutine *` (line 80).

## Invariants

- **INV-tsm-makenode:** "it's recommended that the handler initialize
  the struct with `makeNode(TsmRoutine)` so that all fields are set to
  NULL. This will ensure that no fields are accidentally left
  undefined." [verified-by-code] lines 53-55. The struct may grow in
  future versions; uninitialized garbage in new fields would be a
  silent bug.
- `BeginSampleScan` and `NextSampleTuple` are **mandatory**; the other
  four are optional (the source comment on lines 71-75 marks them
  "can be NULL").
- `parameterTypes` length determines arity; argument-count mismatch
  is caught at parse-analyze, not at execution.

## Notable internals

A TABLESAMPLE handler is a SQL-level function with signature
`tsm_handler() RETURNS tsm_handler` (pseudo-type). It's registered in
`pg_proc` and looked up by `GetTsmRoutine` via the relation's
`SampleScan` plan node.

The `seed` parameter in `BeginSampleScan` (line 35) comes from the
optional `REPEATABLE (seed)` clause. If absent, the executor generates
a per-query seed.

## Trust-boundary / Phase D surface

`tsm_system_rows` and `tsm_system_time` (contrib) implement this API.
A custom TSM extension can register arbitrary `SampleScanGetSampleSize`
behavior, which the planner trusts for cost estimation. Bogus estimates
won't corrupt anything but can DoS the planner (e.g. claiming 0 tuples
forces nested-loop plans elsewhere).

**More concerning:** the `NextSampleBlock` and `NextSampleTuple`
callbacks return block/offset numbers that the executor uses to
**directly fetch heap pages**. A buggy or malicious TSM extension can
return arbitrary `(blockno, offsetno)` pairs; the executor calls
`heap_fetch` on them. There's no bounds check at this API level — the
extension is trusted to stay within `nblocks` / `maxoffset` (the
arguments it was given). If it returns out-of-range values, the
executor will read past the relation or hit dead tuples.

Listed as a Phase-D extension surface anchor (A14 echo).

## Cross-refs

- `nodes/execnodes.h` — `SampleScanState`.
- `nodes/pathnodes.h` — `RelOptInfo`.
- `src/backend/access/tablesample/` — the two built-ins.
- `contrib/tsm_system_rows/`, `contrib/tsm_system_time/` — examples.
- Documentation: `doc/src/sgml/tablesample-method.sgml`.

## Issues

- **ISSUE-doc**: the header says "More function pointers are likely
  to be added in the future" (line 51) — a forward-compat hint
  worth re-stating in any TSM-extension guide.
- **ISSUE-trust**: no API-level documentation that callbacks MUST
  stay within (`nblocks`, `maxoffset`) bounds; relies on extension
  authors reading `nodeSamplescan.c`.
