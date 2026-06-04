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
