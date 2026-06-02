# pg_aggregate.h

- **Source path:** `source/src/include/catalog/pg_aggregate.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "aggregate" system catalog (`pg_aggregate`). One row per aggregate function, supplementing its `pg_proc` entry with transition/final/combine/serial/deserial/moving-aggregate metadata. [from-comment]

## Catalog definition

- `CATALOG(pg_aggregate, 2600, AggregateRelationId)` — no special BKI markings. PK is `aggfnoid` (the pg_proc OID), not a separate oid column. [verified-by-code]
- `FormData_pg_aggregate` typedef; pointer alias `Form_pg_aggregate`. [verified-by-code]
- `DECLARE_TOAST(pg_aggregate, 4159, 4160)` — has a TOAST table for the varlena text columns. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| aggfnoid | regproc | — | `pg_proc` |
| aggkind | char | `BKI_DEFAULT(n)` | — |
| aggnumdirectargs | int16 | `BKI_DEFAULT(0)` | — |
| aggtransfn | regproc | — | `pg_proc` |
| aggfinalfn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggcombinefn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggserialfn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggdeserialfn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggmtransfn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggminvtransfn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggmfinalfn | regproc | `BKI_DEFAULT(-)` | `pg_proc` (OPT) |
| aggfinalextra | bool | `BKI_DEFAULT(f)` | — |
| aggmfinalextra | bool | `BKI_DEFAULT(f)` | — |
| aggfinalmodify | char | `BKI_DEFAULT(r)` | — |
| aggmfinalmodify | char | `BKI_DEFAULT(r)` | — |
| aggsortop | Oid | `BKI_DEFAULT(0)` | `pg_operator` (OPT) |
| aggtranstype | Oid | — | `pg_type` |
| aggtransspace | int32 | `BKI_DEFAULT(0)` | — |
| aggmtranstype | Oid | `BKI_DEFAULT(0)` | `pg_type` (OPT) |
| aggmtransspace | int32 | `BKI_DEFAULT(0)` | — |
| agginitval | text | `BKI_DEFAULT(_null_)` | — (varlena) |
| aggminitval | text | `BKI_DEFAULT(_null_)` | — (varlena) |

The last two live in `#ifdef CATALOG_VARLEN`. [verified-by-code]

## Key declarations beyond FormData

- `aggkind` on-disk char codes (in `EXPOSE_TO_CLIENT_CODE`): `AGGKIND_NORMAL 'n'`, `AGGKIND_ORDERED_SET 'o'`, `AGGKIND_HYPOTHETICAL 'h'`. Macro `AGGKIND_IS_ORDERED_SET(kind)` tests `kind != 'n'`. [verified-by-code]
- `aggfinalmodify`/`aggmfinalmodify` on-disk codes: `AGGMODIFY_READ_ONLY 'r'`, `AGGMODIFY_SHAREABLE 's'`, `AGGMODIFY_READ_WRITE 'w'`. Documented as performance/correctness tradeoff for finalfn behavior. [from-comment]
- Index/syscache: `pg_aggregate_fnoid_index` (PK on aggfnoid), `AGGFNOID` syscache (size 16). [verified-by-code]
- Function prototype: `AggregateCreate(...)` (29-arg constructor). [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_proc.h` (the agg's prokind='a' row, plus all the transfn/finalfn/etc. targets).

## Tally

`[verified-by-code]=7 [from-comment]=2`
