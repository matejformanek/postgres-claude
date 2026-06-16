# catversion.h

- **Source path:** `source/src/include/catalog/catversion.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Defines `CATALOG_VERSION_NO`, the integer stamped into `pg_control` by initdb and re-checked by every backend at startup. A mismatch means the running backend's compiled-in catalog format does not match the data directory's, and the backend refuses to start. Finer-grained than `PG_VERSION` (major-number) checks. [from-comment]

## What this header IS (not a CATALOG)

No `CATALOG(...)` declaration. The entire functional content of this file is a single `#define`. [verified-by-code]

## Key macro

- `CATALOG_VERSION_NO 202605131` — YYYYMMDDN convention (date + sequence-on-that-day). [verified-by-code]

## The bump rule

"If you commit a change that requires an initdb, you should update the catalog version number (as well as notifying the pgsql-hackers mailing list)." Triggered by: editing any `src/include/catalog/*.h` or `*.dat` file in a way that changes a tuple's format or seeded contents; changing tuple-header layout; changing the serialized representation of `pg_node_tree` (i.e. almost any edit to `primnodes.h` / `parsenodes.h`, because parsetrees appear in stored rules and new-style SQL functions). [from-comment]

## Cross-refs

- Consumer: `source/src/include/catalog/pg_control.h` — `ControlFileData.catalog_version_no` field. See `knowledge/files/src/include/catalog/pg_control.h.md`.
- Consumer: `source/src/backend/access/transam/xlog.c` — `ReadControlFile` checks `catalog_version_no` against the compiled-in `CATALOG_VERSION_NO`.
- Producer: `source/src/bin/initdb/initdb.c` writes the value into a fresh `pg_control`.
- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`.

## Tally

`[verified-by-code]=2 [from-comment]=2`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/catalog-conventions.md](../../../../idioms/catalog-conventions.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new built-in aggregate](../../../../scenarios/add-new-aggregate-function.md)
- [Scenario — Add a new built-in SQL function](../../../../scenarios/add-new-builtin-function.md)
- [Scenario — Add a new built-in type cast](../../../../scenarios/add-new-cast.md)
- [Scenario — Add a new built-in scalar data type](../../../../scenarios/add-new-data-type.md)
- [Scenario — Add a new index access method](../../../../scenarios/add-new-index-am.md)
- [Scenario — Add a new Node type](../../../../scenarios/add-new-node-type.md)
- [Scenario — Add a new built-in operator](../../../../scenarios/add-new-operator.md)
- [Scenario — Add a new operator class for an existing index AM](../../../../scenarios/add-new-operator-class.md)
- [Scenario — Add a new `pg_stat_*` view](../../../../scenarios/add-new-pg-stat-view.md)
- [Scenario — Add a new SQL keyword](../../../../scenarios/add-new-sql-keyword.md)
- [Scenario — Add a column to an existing system catalog](../../../../scenarios/add-new-system-catalog-column.md)
- [Scenario — Add a new system view](../../../../scenarios/add-new-system-view.md)
- [Scenario — Bump CATALOG_VERSION_NO](../../../../scenarios/bump-catversion.md)

<!-- scenarios:auto:end -->
