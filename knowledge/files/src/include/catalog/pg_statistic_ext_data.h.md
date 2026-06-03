# pg_statistic_ext_data.h

- **Source path:** `source/src/include/catalog/pg_statistic_ext_data.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "extended statistics data" system catalog (`pg_statistic_ext_data`) — the *computed* serialized statistics blobs (ndistinct / dependencies / MCV / per-expression pg_statistic rows) for each definition in pg_statistic_ext. [from-comment]

## Catalog definition

- `CATALOG(pg_statistic_ext_data, 3429, StatisticExtDataRelationId)` — per-database. [verified-by-code]
- `FormData_pg_statistic_ext_data` typedef; pointer alias `Form_pg_statistic_ext_data`. [verified-by-code]
- `DECLARE_TOAST(pg_statistic_ext_data, 3430, 3431)` — serialized blobs can be large. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_statistic_ext_data_stxoid_inh_index, 3433, ...)` over `(stxoid, stxdinherit)`. [verified-by-code]
- `MAKE_SYSCACHE(STATEXTDATASTXOID, ..., 4)`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| stxoid | Oid | BKI_LOOKUP | pg_statistic_ext |
| stxdinherit | bool | — | — |
| stxdndistinct | pg_ndistinct | (varlena, nullable) | — |
| stxddependencies | pg_dependencies | (varlena, nullable) | — |
| stxdmcv | pg_mcv_list | (varlena, nullable) | — |
| stxdexpr | pg_statistic[1] | (varlena, nullable, array of pg_statistic rows for expressions) | — |

## Key declarations beyond FormData

- None — no macros, no function prototypes, no character constants. The blob types (`pg_ndistinct`, `pg_dependencies`, `pg_mcv_list`) are pseudo-types defined elsewhere. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Definition catalog: `pg_statistic_ext.h.md`
- Related backend: `source/src/backend/statistics/mcv.c`, `source/src/backend/statistics/dependencies.c`, `source/src/backend/statistics/mvdistinct.c`.

## Potential issues

- **[ISSUE-INFO-LEAK: stxdmcv stores verbatim multi-column sample values]** `pg_statistic_ext_data.h:43` — like `pg_statistic.stavalues`, `stxdmcv` (pg_mcv_list) holds multi-column MCV combinations from user data, and the per-expression `stxdexpr` array embeds full pg_statistic rows (so all the standard MCV/histogram leak surfaces apply per-expression too). [inferred]
- **[ISSUE-DOC-GAP: serialized blob formats are on-disk + version-tied but undocumented in header]** `pg_statistic_ext_data.h:41-44` — the `pg_ndistinct` / `pg_dependencies` / `pg_mcv_list` serializations are durable bytes; header points nowhere for format docs. [inferred]

## Tally

`[verified-by-code]=8 [from-comment]=1 [inferred]=2`
