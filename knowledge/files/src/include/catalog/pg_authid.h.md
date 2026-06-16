# pg_authid.h

- **Source path:** `source/src/include/catalog/pg_authid.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'authorization identifier' system catalog (pg_authid). pg_shadow and pg_group are now views on pg_authid." Cluster-wide role storage; contains the hashed password column. `[from-comment]`

## Catalog definition

- `CATALOG(pg_authid,1260,AuthIdRelationId) BKI_SHARED_RELATION BKI_ROWTYPE_OID(2842,AuthIdRelation_Rowtype_Id) BKI_SCHEMA_MACRO` `[verified-by-code]`
- `FormData_pg_authid` / `Form_pg_authid`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| rolname | NameData | — | — |
| rolsuper | bool | — | — (read via `superuser()` only — per header comment) |
| rolinherit | bool | — | — |
| rolcreaterole | bool | — | — |
| rolcreatedb | bool | — | — |
| rolcanlogin | bool | — | — |
| rolreplication | bool | — | — |
| rolbypassrls | bool | — | — |
| rolconnlimit | int32 | — | — (-1 = no limit, per comment) |
| rolpassword | text | — (varlena, nullable) | — |
| rolvaliduntil | timestamptz | — (varlena, nullable) | — |

Per header: "remaining fields may be null; use `heap_getattr` to read them!" `[from-comment]`

## Key declarations beyond FormData

- Indexes: unique `pg_authid_rolname_index`, PK `pg_authid_oid_index`. Syscaches: `AUTHNAME`, `AUTHOID`. `[verified-by-code]`
- No TOAST table declared (despite having two varlena columns including `rolpassword`). `[verified-by-code]`
- No further function prototypes in this header.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_database.h.md` (datdba → here)
- `knowledge/files/src/include/catalog/pg_namespace.h.md` (nspowner → here)
- `knowledge/files/src/include/catalog/pg_class.h.md` (relowner → here)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: no TOAST table on pg_authid]** `pg_authid.h:71` — `rolpassword` is a `text` column with no length cap, yet there is no `DECLARE_TOAST`. SCRAM verifiers fit in a few hundred bytes so this is fine in practice, but a sufficiently long custom auth scheme could in principle overflow a heap tuple. Likely deliberate (avoid TOAST decoding during connection auth, which happens very early); worth confirming and documenting the rationale.
- **[ISSUE-undocumented-invariant: rolsuper "read via superuser() only" hint]** `pg_authid.h:37` — comment warns "read this field via `superuser()` only!" without explaining why (race with role drops? cache coherence?). The contract is left implicit.

## Tally

`[verified-by-code]=3 [from-comment]=2`
