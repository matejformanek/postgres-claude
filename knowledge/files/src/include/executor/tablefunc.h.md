# tablefunc.h

- **Source:** `source/src/include/executor/tablefunc.h` (67 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## Purpose

Declares `TableFuncRoutine` — the pluggable callback bundle used by
nodeTableFuncscan.c to drive XMLTABLE and JSON_TABLE.

## TableFuncRoutine callbacks

- `InitOpaque(state, natts)` — allocate builder state.
- `SetDocument(state, doc)` — load the XML/JSON input.
- `SetNamespace(state, name, uri)` — for XMLTABLE namespaces.
- `SetRowFilter(state, row_filter)` — main row pattern.
- `SetColumnFilter(state, col_filter, colno)` — per-column pattern.
- `FetchRow(state)` — advance to the next row; returns false at EOS.
- `GetValue(state, colno, typid, typmod, isnull)` — pull current row's
  column value.
- `DestroyOpaque(state)` — cleanup.

Two providers ship in core (in `utils/adt/xml.c` and `utils/adt/jsonpath_exec.c`).
Extensions could in principle register more.

## Tags

- [verified-by-code] callback list.
- [from-comment] field documentation at top.
