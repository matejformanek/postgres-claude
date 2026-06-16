# pg_largeobject.h

- **Source path:** `source/src/include/catalog/pg_largeobject.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Large-object chunk storage. Each row is one page (chunk) of a large object's payload; the large object itself is identified by `loid` and exists per `pg_largeobject_metadata`. Comment in struct: "data has variable length, but we allow direct access; see inv_api.c". [verified-by-code] `pg_largeobject.h:38`

## Catalog definition

- `CATALOG(pg_largeobject, 2613, LargeObjectRelationId)` — per-DB; no shared/bootstrap. [verified-by-code] `pg_largeobject.h:32`
- `FormData_pg_largeobject` typedef; pointer alias `Form_pg_largeobject`. [verified-by-code] `pg_largeobject.h:41,50`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| loid | Oid | BKI_LOOKUP | `pg_largeobject_metadata` |
| pageno | int32 | — | — (page number, starting from 0) |
| data | bytea | BKI_FORCE_NOT_NULL | — (may be zero-length) |

Note: no `oid` column; no `#ifdef CATALOG_VARLEN` block (the `bytea` is laid out as the trailing field but the file does not gate it). The struct accesses `data` directly via custom code in `inv_api.c` rather than the normal heap deform path. [from-comment] [verified-by-code] `pg_largeobject.h:38-40`

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_largeobject_loid_pn_index, 2683, ...)` on (loid, pageno). [verified-by-code] `pg_largeobject.h:52`
- Function prototypes (declared here, defined in `inv_api.c`):
  - `extern Oid LargeObjectCreate(Oid loid);` [verified-by-code] `pg_largeobject.h:54`
  - `extern void LargeObjectDrop(Oid loid);` [verified-by-code] `pg_largeobject.h:55`
  - `extern bool LargeObjectExists(Oid loid);` [verified-by-code] `pg_largeobject.h:56`
  - `extern bool LargeObjectExistsWithSnapshot(Oid loid, Snapshot snapshot);` [verified-by-code] `pg_largeobject.h:57`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_largeobject_metadata.h` (owner + ACL — separate catalog)
- Related backend: `src/backend/storage/large_object/inv_api.c`

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: direct bytea access bypasses TOAST]** `pg_largeobject.h:38-40` — comment says "we allow direct access; see inv_api.c"; the page size is hard-coded as `LOBLKSIZE` (BLCKSZ/4) in `large_object.h`. Header gives no hint that this catalog's storage layout is special — anyone wiring up new VARLEN columns here would silently break LO performance. Severity `maybe`, type `undocumented-invariant`. Relevant if data-leak hardening considers reading large-object pages without going through `lo_*` permission checks.

## Tally

`[verified-by-code]=8 [from-comment]=2`
