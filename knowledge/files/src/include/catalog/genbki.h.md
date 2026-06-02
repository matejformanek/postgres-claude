# genbki.h

- **Source path:** `source/src/include/catalog/genbki.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Required include file for all POSTGRES catalog header files. genbki.h defines CATALOG(), BKI_BOOTSTRAP and related macros so that the catalog header files can be read by the C compiler. (These same words are recognized by genbki.pl to build the BKI bootstrap file from these header files.)" [from-comment, genbki.h:3-10]

## Key macros

- `BEGIN_CATALOG_STRUCT` / `END_CATALOG_STRUCT` — wrap struct definitions with `_Pragma("pack(push,4)")` on platforms where `ALIGNOF_DOUBLE < ALIGNOF_INT64_T` (AIX), no-op elsewhere. Ensures the C struct layout matches PG's tuple-forming/deforming rules. [verified-by-code, genbki.h:33-39]
- `CATALOG(name, oid, oidmacro)` — introduces a catalog struct. Expands to `typedef struct FormData_<name>`. [verified-by-code, genbki.h:42]
- `BKI_BOOTSTRAP` / `BKI_SHARED_RELATION` / `BKI_ROWTYPE_OID(oid,m)` / `BKI_SCHEMA_MACRO` — empty for C compiler; genbki.pl recognises them on the same source line as CATALOG().
- `BKI_FORCE_NULL` / `BKI_FORCE_NOT_NULL` / `BKI_DEFAULT(v)` / `BKI_ARRAY_DEFAULT(v)` — per-attribute markers.
- `BKI_LOOKUP(catalog)` / `BKI_LOOKUP_OPT(catalog)` — symbolic-name resolution. genbki.pl uses this to know how to perform name lookups in the initial data, and "feeds into regression-test validity checks." `_OPT` allows zero (no reference). [from-comment, genbki.h:58-66]
- `DECLARE_TOAST(rel, toast_oid, index_oid)` / `DECLARE_TOAST_WITH_MACRO(...)` — issue a BootstrapToastTable directive in the BKI. Toast OIDs must be hardcoded so shared-catalog toasts are stable across initdb. [from-comment, genbki.h:67-86]
- `DECLARE_INDEX(name, oid, oidmacro, decl)` / `DECLARE_UNIQUE_INDEX(...)` / `DECLARE_OID_DEFINING_MACRO(name,oid)` — catalog index declarations (lower in this file).

## Tally

`[verified-by-code]=2 [from-comment]=3`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/catalog-conventions.md](../../../../idioms/catalog-conventions.md)