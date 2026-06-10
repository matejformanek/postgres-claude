# `executor/nodeTableFuncscan.h` — TABLE function scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeTableFuncscan.h`)

## Role
Declares executor entry points for `TableFuncScan` — the scan node for SQL/JSON `JSON_TABLE` and SQL/XML `XMLTABLE` constructs. Drives the row-by-row materialization that the parser-generated `TableFunc` node specifies, via the routing layer in `executor/tablefunc.h`.

## Public API
- `ExecInitTableFuncScan(TableFuncScan *, EState *, int eflags)` — nodeTableFuncscan.h:19
- `ExecEndTableFuncScan(TableFuncScanState *)` — nodeTableFuncscan.h:20
- `ExecReScanTableFuncScan(TableFuncScanState *)` — nodeTableFuncscan.h:21

## Phase D
External-data trust (A7 echo). The underlying `XMLTABLE` path runs libxml2 on user input — XXE / DTD / billion-laughs attack surface unless `XML_PARSE_NOENT` and `XML_PARSE_HUGE` are correctly handled in `utils/adt/xml.c`. The `JSON_TABLE` path uses `jsonapi.c` and is less exposed because the JSON tokenizer doesn't follow external references, but recursive structures can still be DoS vectors. Document-size limits and parse-time bounds are the relevant defenses.

## Cross-refs
- Plan node: `TableFuncScan` in `nodes/plannodes.h`
- Parse-tree node: `TableFunc` in `nodes/primnodes.h`
- State node: `TableFuncScanState` in `nodes/execnodes.h`
- Routing: `executor/tablefunc.h`
- `.c` impl: `source/src/backend/executor/nodeTableFuncscan.c`
- XML/JSON backends: `utils/adt/xml.c`, `common/jsonapi.c`
