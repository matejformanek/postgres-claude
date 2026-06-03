# pg_statistic_ext.h

- **Source path:** `source/src/include/catalog/pg_statistic_ext.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "extended statistics" system catalog (`pg_statistic_ext`) — the *definitions* of CREATE STATISTICS objects (which columns / which kinds requested), not the computed data. [from-comment]

## Catalog definition

- `CATALOG(pg_statistic_ext, 3381, StatisticExtRelationId)` — per-database. [verified-by-code]
- `FormData_pg_statistic_ext` typedef; pointer alias `Form_pg_statistic_ext`. [verified-by-code]
- `DECLARE_TOAST(pg_statistic_ext, 3439, 3440)`. [verified-by-code]
- Indexes: PKEY on `oid` (3380); UNIQUE on `(stxname, stxnamespace)` (3997); non-unique on `stxrelid` (3379). [verified-by-code]
- Syscaches: `STATEXTOID`, `STATEXTNAMENSP`. [verified-by-code]
- `DECLARE_ARRAY_FOREIGN_KEY((stxrelid, stxkeys), pg_attribute, (attrelid, attnum))`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| stxrelid | Oid | BKI_LOOKUP | pg_class |
| stxname | NameData | — | — |
| stxnamespace | Oid | BKI_LOOKUP | pg_namespace |
| stxowner | Oid | BKI_LOOKUP | pg_authid |
| stxkeys | int2vector | BKI_FORCE_NOT_NULL | — (array FK to pg_attribute) |
| stxstattarget | int16 | BKI_DEFAULT(_null_), BKI_FORCE_NULL (varlena block) | — |
| stxkind | char[1] | BKI_FORCE_NOT_NULL (varlena block) | — |
| stxexprs | pg_node_tree | (varlena, nullable) | — |

## Key declarations beyond FormData

- `STATS_EXT_NDISTINCT  'd'` — n-distinct coefficients. [verified-by-code]
- `STATS_EXT_DEPENDENCIES 'f'` — functional dependencies. [verified-by-code]
- `STATS_EXT_MCV         'm'` — multivariate MCV list. [verified-by-code]
- `STATS_EXT_EXPRESSIONS 'e'` — per-expression statistics. [verified-by-code]
- **These single-char codes are on-disk values** appearing in `stxkind[]`; renaming them is a catalog-format break. Header does not call this out explicitly. [inferred]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companion data table: `pg_statistic_ext_data.h.md`
- Related backend: `source/src/backend/statistics/extended_stats.c`, `source/src/backend/commands/statscmds.c`.

## Potential issues

- **[ISSUE-ONDISK-CONTRACT: stxkind character codes not flagged as on-disk]** `pg_statistic_ext.h:88-91` — the four `STATS_EXT_*` chars are stored in the catalog and parsed by extended-stats code. Header lacks a "do not change these letters" warning analogous to pg_trigger's tgenabled. [inferred]

## Tally

`[verified-by-code]=10 [from-comment]=1 [inferred]=2`
