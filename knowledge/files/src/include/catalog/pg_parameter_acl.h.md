# pg_parameter_acl.h

- **Source path:** `source/src/include/catalog/pg_parameter_acl.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

ACLs for configuration parameters (GUCs). Backs `GRANT SET / ALTER SYSTEM ON PARAMETER`. A row is created lazily the first time a GUC name has a non-default ACL; the GUC itself need not have been seen yet by the running backend.

## Catalog definition

- `CATALOG(pg_parameter_acl, 6243, ParameterAclRelationId) BKI_SHARED_RELATION` — **shared catalog**. [verified-by-code] `pg_parameter_acl.h:32`
- `FormData_pg_parameter_acl` typedef; pointer alias `Form_pg_parameter_acl`. [verified-by-code] `pg_parameter_acl.h:43,53`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| parname | text (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |
| paracl | aclitem[1] (varlena) | BKI_DEFAULT(_null_) | — (under `#ifdef CATALOG_VARLEN`) |

## Key declarations beyond FormData

- `DECLARE_TOAST_WITH_MACRO(pg_parameter_acl, 6244, 6245, PgParameterAclToastTable, PgParameterAclToastIndex)` — `_WITH_MACRO` variant required for shared catalogs. [verified-by-code] `pg_parameter_acl.h:55`
- `DECLARE_UNIQUE_INDEX(pg_parameter_acl_parname_index, 6246, ...)` on (parname). [verified-by-code] `pg_parameter_acl.h:57`
- `DECLARE_UNIQUE_INDEX_PKEY(pg_parameter_acl_oid_index, 6247, ...)`. [verified-by-code] `pg_parameter_acl.h:58`
- `MAKE_SYSCACHE(PARAMETERACLNAME, ..., 4)` and `MAKE_SYSCACHE(PARAMETERACLOID, ..., 4)`. [verified-by-code] `pg_parameter_acl.h:60-61`
- Function prototypes (declared here, defined in `pg_parameter_acl.c`):
  - `extern Oid ParameterAclLookup(const char *parameter, bool missing_ok);` [verified-by-code] `pg_parameter_acl.h:63`
  - `extern Oid ParameterAclCreate(const char *parameter);` [verified-by-code] `pg_parameter_acl.h:64`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_authid.h` (grantees in `paracl`)
- Related backend: `src/backend/catalog/pg_parameter_acl.c`, `src/backend/utils/misc/guc.c`

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: parname is the raw user-supplied string, no canonicalization documented]** `pg_parameter_acl.h:38` — GUC names are case-insensitive and may have dot-qualified extension prefixes (`pg_stat_statements.track`). The header doesn't document whether `parname` is lower-cased or normalized before storage; the unique index uses `text_ops` (case-sensitive). A divergent canonicalization between GRANT and SET would create a silent privilege bypass. Severity `maybe`, type `correctness`. Worth verifying in `ParameterAclCreate` / `ParameterAclLookup` — flag for the data-leak hardening project.
- **[ISSUE-question: paracl BKI_DEFAULT(_null_) — when does a row exist with NULL paracl?]** `pg_parameter_acl.h:41` — most ACL catalogs make paracl NOT NULL. Here it's nullable with default NULL. Either a row is only created when an ACL is granted (so paracl is always non-null in practice) or NULL has a special meaning. Header doesn't explain. Severity `nit`, type `question`.

## Tally

`[verified-by-code]=11 [inferred]=2`
