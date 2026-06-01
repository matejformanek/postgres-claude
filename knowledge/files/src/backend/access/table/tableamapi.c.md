# tableamapi.c

- **Source path:** `source/src/backend/access/table/tableamapi.c`
- **Lines:** 148
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tableam.h` (the `TableAmRoutine` struct), `heap/heapam_handler.c` (only in-tree AM), `commands/defrem.c` (`get_table_am_oid`).

## Purpose

Two responsibilities:

1. `GetTableAmRoutine(amhandler)` — Call the AM's handler function, validate that all 30+ mandatory callbacks are non-NULL. This is the table-AM analogue of `index/amapi.c::GetIndexAmRoutine`.
2. `check_default_table_access_method` — GUC validator for `default_table_access_method`.

[verified-by-code]

## Top-of-file comment

> "Support routines for API for Postgres table access methods" — brief; the substantive documentation lives in `tableam.h` and `tableam.sgml`. [from-comment, tableamapi.c:1-10]

## Public surface

- `GetTableAmRoutine` (27) — `OidFunctionCall0(amhandler)`, expect `Node(TableAmRoutine)` back, Assert each mandatory callback. The Assert list (44-94) is the **definitive enumeration** of what a table AM is required to implement: scan_begin/end/rescan/getnextslot, parallel-scan setup, index-fetch (begin/reset/end/tuple), tuple operations (fetch_row_version/tid_valid/get_latest_tid/satisfies_snapshot/index_delete_tuples/insert/insert_speculative/complete_speculative/multi_insert/delete/update/lock), relation operations (set_new_filelocator, nontransactional_truncate, copy_data, copy_for_cluster, vacuum), ANALYZE callbacks (scan_analyze_next_block/tuple), index build (index_build_range_scan/index_validate_scan), relation_size, relation_needs_toast_table, relation_estimate_size, sample-scan callbacks. [verified-by-code, tableamapi.c:27-97]
- `check_default_table_access_method` (101) — GUC `check_hook`: rejects empty string and anything ≥ NAMEDATALEN; if connected to a database, looks up `pg_am` for `amname` and errors (or emits NOTICE for `PGC_S_TEST`) if not found.

## Key invariants

- Handlers MUST return a statically-allocated `TableAmRoutine *`. [from-comment, tableamapi.c:22-25]
- The Assert list defines the AM contract: any new mandatory callback must be added here AND in every handler. Adding one here without updating handlers will crash assert-enabled builds at AM-handler invocation. [from-comment, tableamapi.c:39-43]
- `tuple_insert_speculative` and `tuple_complete_speculative` are marked "could be made optional, but would require throwing error during parse-analysis." — i.e. currently mandatory because the parser doesn't know which AM will be used yet. [from-comment, tableamapi.c:66-70]
- `check_default_table_access_method` is tolerant: outside transactions / before DB connection, it accepts any non-empty string "on faith" — needed because the GUC is parsed before catalog access is available. [from-comment, tableamapi.c:117-122]

## Cross-references

- `GetTableAmRoutine` is called by `relcache.c::RelationInitTableAccessMethod` when building a relcache entry.
- `check_default_table_access_method` is registered as the check_hook for the GUC in `utils/misc/guc_tables.c`.
- The handler functions themselves (e.g. `heap_tableam_handler`) live in each AM's `*_handler.c` file.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
