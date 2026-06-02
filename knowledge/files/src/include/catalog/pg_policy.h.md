# pg_policy.h

- **Source path:** `source/src/include/catalog/pg_policy.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Row-Level Security (RLS) policy definitions. One row per `CREATE POLICY` statement: ties a relation, a command class, a permissive/restrictive flag, applicable roles, and USING + WITH CHECK quals.

## Catalog definition

- `CATALOG(pg_policy, 3256, PolicyRelationId)` — per-DB; no shared/bootstrap. [verified-by-code] `pg_policy.h:31`
- `FormData_pg_policy` typedef; pointer alias `Form_pg_policy`. [verified-by-code] `pg_policy.h:46,55`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| polname | NameData | — | — |
| polrelid | Oid | BKI_LOOKUP | `pg_class` |
| polcmd | char | — | — (one of `ACL_*_CHR`, or `'*'` for all) |
| polpermissive | bool | — | — (true = permissive, false = restrictive) |
| polroles | Oid[1] (varlena) | BKI_LOOKUP_OPT, BKI_FORCE_NOT_NULL | `pg_authid` (under `#ifdef CATALOG_VARLEN`; 0 entry = PUBLIC) |
| polqual | pg_node_tree (varlena) | — | — (USING quals; under `#ifdef CATALOG_VARLEN`) |
| polwithcheck | pg_node_tree (varlena) | — | — (WITH CHECK quals; under `#ifdef CATALOG_VARLEN`) |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_policy, 4167, 4168)`. [verified-by-code] `pg_policy.h:57`
- `DECLARE_UNIQUE_INDEX_PKEY(pg_policy_oid_index, 3257, ...)`. [verified-by-code] `pg_policy.h:59`
- `DECLARE_UNIQUE_INDEX(pg_policy_polrelid_polname_index, 3258, ...)` on (polrelid, polname). [verified-by-code] `pg_policy.h:60`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_class.h` (RLS-related fields `relrowsecurity`, `relforcerowsecurity`)
- Related backend: `src/backend/rewrite/rowsecurity.c`, `src/backend/commands/policy.c`

## Potential issues

- **[ISSUE-undocumented-invariant: polcmd char values come from ACL_*_CHR not a local enum]** `pg_policy.h:37` — `polcmd` holds an ACL char ('r' SELECT, 'a' INSERT, 'w' UPDATE, 'd' DELETE) plus `'*'` for ALL. These are **on-disk values** defined in `parsenodes.h` / `acl.h`. Header refers to "ACL_*_CHR" but doesn't pin down where they live or warn about the on-disk dependency. Severity `maybe`, type `undocumented-invariant`. Relevant for the data-leak hardening project — any divergence between `polcmd` and the SELECT/UPDATE/DELETE classification used during query rewriting is a candidate RLS bypass.
- **[ISSUE-question: polroles with embedded 0 means PUBLIC, but BKI_LOOKUP_OPT semantics on an array element are unclear]** `pg_policy.h:42` — comment says "zero means PUBLIC"; the array uses `BKI_LOOKUP_OPT(pg_authid)` which is normally for scalar nullable lookups. Whether genbki / pg_dump correctly handle an Oid[] with mixed real-role and zero entries deserves verification. Severity `maybe`, type `question`.

## Tally

`[verified-by-code]=11 [from-comment]=2 [inferred]=1`
