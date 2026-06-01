# pg_parameter_acl.c

- **Source path:** `source/src/backend/catalog/pg_parameter_acl.c`
- **Lines:** ~90
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_parameter_acl relation." Shared catalog of GUC parameter ACLs (`GRANT SET ON PARAMETER name TO role`). Lazy-row creation: row is only inserted when first GRANT happens for that parameter; lookup falls back to default (superuser-only) when no row exists.

## Public surface

- `ParameterAclLookup` — by-name lookup (returns InvalidOid if no row, signalling default ACL).
- `ParameterAclCreate` — insert-or-find row for the given parameter name.
- `RemoveParameterAclById` — drop row.

## Confidence tag tally

`[inferred]=3`
