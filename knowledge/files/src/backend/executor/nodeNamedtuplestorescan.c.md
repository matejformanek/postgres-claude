# nodeNamedtuplestorescan.c

- **Source:** `source/src/backend/executor/nodeNamedtuplestorescan.c` (≈170 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Scans a **named** Tuplestorestate exposed by the query environment
(`QueryEnvironment`). Used by **transition tables** in row-level triggers:
`REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table` puts a
named tuplestore in the env, then plain SQL inside the trigger function
can read it via `NamedTuplestoreScan`.

## Mechanics

- Init: look up the named entry in `estate->es_queryEnv`, take a read
  pointer.
- Per call: `tuplestore_gettupleslot` to grab the next row.

## Tags

- [verified-by-code] queryEnvironment lookup + read pointer.
- [from-comment] NamedTuplestoreScanNext docstring.
