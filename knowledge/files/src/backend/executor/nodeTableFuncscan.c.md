# nodeTableFuncscan.c

- **Source:** `source/src/backend/executor/nodeTableFuncscan.c` (≈430 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Scans the output of `XMLTABLE(...)` and SQL/JSON `JSON_TABLE(...)`. These
parser-level constructs are tabular functions that read structured input
(XML doc, JSON doc) and emit one row per "row pattern" match.

## Mechanics

- Driver uses a pluggable `TableFuncRoutine` (`executor/tablefunc.h`) chosen
  by `tablefunctype` (TFT_XMLTABLE or TFT_JSON_TABLE).
- Init: evaluate the docExpr to get the input document; per-column
  expressions are compiled to ExprStates.
- Drain into a Tuplestorestate by repeated calls to
  `routine->FetchRow(state, slot)`.
- Per ExecTableFuncScan call: read from tuplestore.

JSON_TABLE specifically uses jsonpath evaluation and the SQL/JSON
NESTED / PLAN clauses to produce hierarchical row patterns.

## Tags

- [verified-by-code] TableFuncRoutine dispatch.
- [from-comment] interface list at top.
