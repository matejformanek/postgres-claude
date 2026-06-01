# foreigncmds.c

- **Source path:** `source/src/backend/commands/foreigncmds.c`
- **Lines:** 1724
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Foreign-data wrapper/server creation/manipulation commands." [from-comment, foreigncmds.c:3-4] CREATE/ALTER/DROP FOREIGN DATA WRAPPER, SERVER, USER MAPPING — the catalog side of FDWs. The runtime side (`fdw_handler`, executor callbacks) lives in `foreign/foreign.c` and `foreign/fdwapi.c`.

## Public surface

- `CreateForeignDataWrapper`, `AlterForeignDataWrapper`, `RemoveForeignDataWrapperById` — pg_foreign_data_wrapper.
- `CreateForeignServer`, `AlterForeignServer`, `RemoveForeignServerById` — pg_foreign_server.
- `CreateUserMapping`, `AlterUserMapping`, `RemoveUserMappingById` — pg_user_mapping.
- `ImportForeignSchema` — IMPORT FOREIGN SCHEMA; calls the FDW's `ImportForeignSchema` callback which returns a list of CREATE FOREIGN TABLE statements, then `ProcessUtility`s each.
- Helpers: `transformGenericOptions` (parse OPTIONS clauses with ADD/SET/DROP semantics), `optionListToArray` (convert to text[] for pg_*.options storage).

## OPTIONS clause semantics

Every FDW catalog object stores `options text[]` of "key=value" strings. ALTER allows `OPTIONS (ADD k v, SET k v, DROP k)` semantics — ADD errors if key exists, SET errors if absent, DROP must exist. The validator function on the FDW (set at CREATE FDW time) gets a chance to vet the final list.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
