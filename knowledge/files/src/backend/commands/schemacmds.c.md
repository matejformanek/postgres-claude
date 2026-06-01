# schemacmds.c

- **Source path:** `source/src/backend/commands/schemacmds.c`
- **Lines:** 443
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Schema creation/manipulation commands" [from-comment, schemacmds.c:3-4]: CREATE SCHEMA, DROP SCHEMA (via dropcmds.c), ALTER SCHEMA RENAME/OWNER.

## Public surface

- `CreateSchemaCommand` — entry from utility. CREATE SCHEMA with embedded sub-statements: parses out the `CreateStmt`/`GrantStmt`/`ViewStmt`/etc. sub-commands and dispatches each through `ProcessUtility` recursively, with the new schema pre-pended onto `search_path` so unqualified names resolve correctly.
- `RenameSchema` — straightforward `pg_namespace` rename; rejects if any object in the schema would now be ambiguous.
- `AlterSchemaOwner` / `AlterSchemaOwner_oid` / `AlterSchemaOwner_internal` — owner change; uses the standard "new owner must be a member" rule.

## Quirk

The grammar allows `CREATE SCHEMA AUTHORIZATION foo` with no schema name — the new schema is then named after the role. Worth knowing if you grep for this case.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
