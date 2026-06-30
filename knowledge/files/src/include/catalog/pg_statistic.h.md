# pg_statistic.h

- **Source path:** `source/src/include/catalog/pg_statistic.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "statistics" system catalog (`pg_statistic`) — per-(relation, attribute, inheritance) column statistics emitted by ANALYZE. [from-comment]

## Catalog definition

- `CATALOG(pg_statistic, 2619, StatisticRelationId)` — no BKI_BOOTSTRAP, no BKI_SHARED_RELATION; per-database. [verified-by-code]
- `FormData_pg_statistic` typedef; pointer alias `Form_pg_statistic`. [verified-by-code]
- `DECLARE_TOAST(pg_statistic, 2840, 2841)` — TOAST sidecar (the stavalues/stanumbers arrays can be large). [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_statistic_relid_att_inh_index, 2696, ...)` over `(starelid, staattnum, stainherit)`. [verified-by-code]
- `MAKE_SYSCACHE(STATRELATTINH, ..., 128)`. [verified-by-code]
- `DECLARE_FOREIGN_KEY((starelid, staattnum), pg_attribute, (attrelid, attnum))`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| starelid | Oid | BKI_LOOKUP | pg_class |
| staattnum | int16 | — | — |
| stainherit | bool | — | — |
| stanullfrac | float4 | — | — |
| stawidth | int32 | — | — |
| stadistinct | float4 | — | — |
| stakind1..5 | int16 | — | — |
| staop1..5 | Oid | BKI_LOOKUP_OPT | pg_operator |
| stacoll1..5 | Oid | BKI_LOOKUP_OPT | pg_collation |
| stanumbers1..5 | float4[] | (varlena) | — |
| stavalues1..5 | anyarray | (varlena) | — |

## Key declarations beyond FormData

- `STATISTIC_NUM_SLOTS = 5` — number of (kind, op, coll, numbers, values) tuples. [verified-by-code]
- Slot-kind integer constants (1-99 reserved for core; 100-199 PostGIS; 200-299 ESRI; 300-9999 future; 10000-30000 private): `STATISTIC_KIND_MCV=1`, `STATISTIC_KIND_HISTOGRAM=2`, `STATISTIC_KIND_CORRELATION=3`, `STATISTIC_KIND_MCELEM=4`, `STATISTIC_KIND_DECHIST=5`, `STATISTIC_KIND_RANGE_LENGTH_HISTOGRAM=6`, `STATISTIC_KIND_BOUNDS_HISTOGRAM=7`. **These integers are on-disk values** — third parties consume them via `get_attstatsslot()`; renumbering would silently corrupt PostGIS et al. [verified-by-code]
- Guidance comment: code reading pg_statistic should search the `stakind` fields rather than assume a slot ordering. [from-comment]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related backend: `source/src/backend/statistics/`, `source/src/backend/commands/analyze.c`, `source/src/backend/utils/cache/lsyscache.c` (`get_attstatsslot`).
- Related per-file docs: `pg_statistic_ext.h.md`, `pg_statistic_ext_data.h.md`.

## Potential issues

- **[ISSUE-INFO-LEAK: pg_statistic.stavalues holds verbatim sample values from user data]** `pg_statistic.h:121-125` — `stavaluesN anyarray` contains MCV samples and histogram bin boundaries copied straight from the column. Combined with the relation-wide read permission required to query pg_statistic on a table, this is the long-known surface that motivated the `pg_stats` view's role-aware filter, but the underlying catalog row exposes the values verbatim. The header notes the slot-kind contract but does NOT call out the info-leak surface. [verified-by-code]
- **[ISSUE-ONDISK-CONTRACT: slot-kind integers are an unwritten on-disk + cross-project contract]** `pg_statistic.h:166-181` — header documents the allocation range but never says "do not renumber existing values"; an editor could plausibly think kind codes are internal. They are not — PostGIS/ESRI ship typanalyze code that emits these integers. [inferred]

## Tally

`[verified-by-code]=9 [from-comment]=2 [inferred]=1`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/analyze-mcv-histogram-correlation.md](../../../../idioms/analyze-mcv-histogram-correlation.md)
