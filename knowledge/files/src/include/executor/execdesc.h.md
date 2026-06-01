# execdesc.h

- **Source:** `source/src/include/executor/execdesc.h` (72 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## Purpose

Defines `QueryDesc` — the bag-of-everything the executor needs to run a
query. Tied between tcop / executor / SPI / SQL functions.

## QueryDesc fields

- `operation` (CmdType — SELECT/INSERT/UPDATE/DELETE/MERGE/UTILITY).
- `plannedstmt` (PlannedStmt*).
- `sourceText` (the query text, for executor_errposition + EXPLAIN).
- `snapshot`, `crosscheck_snapshot` (the latter for RI constraint checks).
- `dest` (DestReceiver*).
- `params` (ParamListInfo).
- `queryEnv` (QueryEnvironment* — for named tuplestores / transition tables).
- `instrument_options` — INSTRUMENT_TIMER/INSTRUMENT_ROWS/BUFFERS/WAL.
- After ExecutorStart: `tupDesc`, `estate`, `planstate` populated.
- `already_executed` — set true at first ExecutorRun for repeat-call guards.

## Lifecycle helpers

- `CreateQueryDesc(plannedstmt, sourceText, snapshot, crosscheck, dest, params, queryEnv, instrument_options)`.
- `FreeQueryDesc(qdesc)`.

QueryDescs for **utility statements** are allowed (SQL functions store one
per command) but must not be passed to the executor — `ProcessUtility`
handles them. [from-comment file head]

## Tags

- [verified-by-code] all field names.
- [from-comment] utility-statement caveat.
