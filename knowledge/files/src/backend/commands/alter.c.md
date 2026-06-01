# alter.c

- **Source path:** `source/src/backend/commands/alter.c`
- **Lines:** 1075
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Drivers for generic alter commands" [from-comment, alter.c:3-4] — the catalog-agnostic `ALTER OWNER`, `ALTER ... RENAME`, `ALTER ... SET SCHEMA`, and `ALTER ... DEPENDS ON EXTENSION` dispatchers. Each switches on `ObjectType` (or `classId`) and dispatches to the per-object-class catalog mutator (e.g. `AlterFunctionOwner_oid`, `AlterTypeOwner`).

## Public surface

- `ExecRenameStmt` — RENAME for any object class; switches on `RenameStmt.renameType`.
- `ExecAlterObjectSchemaStmt` — `ALTER ... SET SCHEMA newschema`; calls `AlterObjectNamespace_oid` after object-type-specific permission checks.
- `AlterObjectNamespace_oid` — internal helper: update the catalog tuple's `*relnamespace`/`*pronamespace`/etc., move dependent objects (indexes, sequences owned by a table, etc.), invalidate caches.
- `ExecAlterOwnerStmt` — `ALTER ... OWNER TO newrole`; per-class dispatch.
- `ExecAlterObjectDependsStmt` — record/remove dependency on a named extension.

## Cross-cutting behaviour

The actual ACL transfer (revoke from old owner, grant to new) and the membership-check policy ("you must be member of new owner role") live here and are uniform across object types — a common gotcha when adding a new object class is forgetting to teach `ExecAlterOwnerStmt` about it.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
