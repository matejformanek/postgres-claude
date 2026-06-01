# amcmds.c

- **Source path:** `source/src/backend/commands/amcmds.c`
- **Lines:** 269
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines for SQL commands that manipulate access methods." [from-comment, amcmds.c:3-4] CREATE / DROP ACCESS METHOD — registers a new index AM or table AM by pointing at its `handler` function (which returns an `IndexAmRoutine` or `TableAmRoutine` C struct).

## Public surface

- `CreateAccessMethod` — pg_am row creation; `amtype = 'i'` (index) or `'t'` (table).
- `lookup_am_handler_func` (static) — verify the handler function exists, returns the right pseudo-type (`index_am_handler` or `table_am_handler`), and is callable.
- `get_am_oid`, `get_am_name`, `get_am_type_oid`, `get_am_type_string` — utility lookups consumed elsewhere.

## Confidence tag tally

`[verified-by-code]=2 [from-comment]=1`
