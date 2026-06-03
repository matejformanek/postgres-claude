# binary_upgrade.h

- **Source path:** `source/src/include/catalog/binary_upgrade.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Variables used for binary upgrades." Declares the `binary_upgrade_next_*` global variables that `pg_upgrade` (via `pg_dump --binary-upgrade`) uses to force specific OIDs / RelFileNumbers onto catalog rows during reload, so the new cluster preserves the old cluster's object identifiers. [from-comment]

## What this header IS (not a CATALOG)

No `CATALOG(...)` declaration. The file is a small header of `extern PGDLLIMPORT` globals; their definitions live in `source/src/backend/catalog/heap.c` and a few peers, and they are set by `binary_upgrade_set_next_*` SQL functions (in `pg_upgrade_support.c`) that pg_dump emits into the upgrade script. [inferred]

## Declared globals

- `binary_upgrade_next_pg_tablespace_oid` (Oid) — for the next `CREATE TABLESPACE`.
- `binary_upgrade_next_pg_type_oid` (Oid) — for the next base/composite type.
- `binary_upgrade_next_array_pg_type_oid` (Oid) — for the auto-created array type.
- `binary_upgrade_next_mrng_pg_type_oid` (Oid) — for the auto-created multirange type of a range.
- `binary_upgrade_next_mrng_array_pg_type_oid` (Oid) — for the multirange's array type.
- `binary_upgrade_next_heap_pg_class_oid` (Oid) — next heap relation's pg_class.oid.
- `binary_upgrade_next_heap_pg_class_relfilenumber` (RelFileNumber) — next heap's relfilenode.
- `binary_upgrade_next_index_pg_class_oid` (Oid) — next index's pg_class.oid.
- `binary_upgrade_next_index_pg_class_relfilenumber` (RelFileNumber).
- `binary_upgrade_next_toast_pg_class_oid` (Oid) — next TOAST table's pg_class.oid.
- `binary_upgrade_next_toast_pg_class_relfilenumber` (RelFileNumber).
- `binary_upgrade_next_pg_enum_oid` (Oid) — next enum label oid.
- `binary_upgrade_next_pg_authid_oid` (Oid) — next role oid.
- `binary_upgrade_record_init_privs` (bool) — when true, pg_init_privs entries are recorded as if from `CREATE EXTENSION`. [verified-by-code]

All are `PGDLLIMPORT` so extensions / pg_upgrade-support .so files on Windows can read them. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Setter SQL funcs: `source/src/backend/utils/adt/pg_upgrade_support.c`.
- Consumers: `source/src/backend/catalog/heap.c` (uses the heap/index/toast oid + relfilenumber globals in `heap_create_with_catalog` / `heap_create`), `source/src/backend/catalog/pg_type.c`, `source/src/backend/commands/tablespace.c`, `source/src/backend/commands/typecmds.c`, `source/src/backend/commands/user.c`, `source/src/backend/catalog/pg_enum.c`.
- Tool: `source/src/bin/pg_upgrade/` and `source/src/bin/pg_dump/pg_dump.c` (--binary-upgrade emits the setter calls).

## Tally

`[verified-by-code]=2 [from-comment]=1 [inferred]=1`
