# pg_collation.h

- **Source path:** `source/src/include/catalog/pg_collation.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Definition of the "collation" system catalog (`pg_collation`). One row per named collation (provider-specific: builtin, libc, ICU). [from-comment]

## Catalog definition

- `CATALOG(pg_collation, 3456, CollationRelationId)` — no special BKI markings. [verified-by-code]
- `FormData_pg_collation` typedef; pointer alias `Form_pg_collation`. [verified-by-code]
- `DECLARE_TOAST(pg_collation, 6175, 6176)`. [verified-by-code]

## Columns (verbatim from the struct)

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| collname | NameData | — | — |
| collnamespace | Oid | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| collowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| collprovider | char | — | — |
| collisdeterministic | bool | `BKI_DEFAULT(t)` | — |
| collencoding | int32 | — | — (-1 = "all") |
| collcollate | text | `BKI_DEFAULT(_null_)` | — (varlena) |
| collctype | text | `BKI_DEFAULT(_null_)` | — (varlena) |
| colllocale | text | `BKI_DEFAULT(_null_)` | — (varlena) |
| collicurules | text | `BKI_DEFAULT(_null_)` | — (varlena) |
| collversion | text | `BKI_DEFAULT(_null_)` | — (varlena) |

The varlena columns live in `#ifdef CATALOG_VARLEN`. [verified-by-code]

## Key declarations beyond FormData

- `collprovider` on-disk char codes (in `EXPOSE_TO_CLIENT_CODE`): `COLLPROVIDER_DEFAULT 'd'`, `COLLPROVIDER_BUILTIN 'b'`, `COLLPROVIDER_ICU 'i'`, `COLLPROVIDER_LIBC 'c'`. [verified-by-code]
- Inline helper `collprovider_name(char c)` returns "builtin"/"icu"/"libc"/"???" — note `COLLPROVIDER_DEFAULT` is not handled (returns "???"). [verified-by-code]
- Indexes: `pg_collation_name_enc_nsp_index` on `(collname, collencoding, collnamespace)`, `pg_collation_oid_index` (PK). [verified-by-code]
- Syscaches: `COLLNAMEENCNSP` (8), `COLLOID` (8). [verified-by-code]
- Function prototype: `CollationCreate(...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_attribute.h` (attcollation), `pg_type.h` (typcollation), `utils/adt/pg_locale.c`.

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: collprovider_name omits COLLPROVIDER_DEFAULT]** `pg_collation.h:79-93` — the inline switch returns "???" for `'d'`. May be intentional (default never appears in stored rows, only in CREATE COLLATION parsing) but the header doesn't say so.

## Tally

`[verified-by-code]=8 [from-comment]=1`
