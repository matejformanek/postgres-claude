# dropcmds.c

- **Source path:** `source/src/backend/commands/dropcmds.c`
- **Lines:** 525
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Handle various 'DROP' operations." [from-comment, dropcmds.c:3-4] The generic-DROP dispatcher for object types that don't need their own specialised drop file. DROP TABLE/INDEX live in tablecmds.c; DROP DATABASE in dbcommands.c. This file handles DROP TYPE, DROP DOMAIN, DROP FUNCTION/PROCEDURE/ROUTINE, DROP AGGREGATE, DROP OPERATOR, DROP RULE, DROP TRIGGER, DROP CAST, DROP COLLATION, DROP CONVERSION, DROP TEXT SEARCH …, DROP SCHEMA, DROP FOREIGN DATA WRAPPER / SERVER, DROP TRANSFORM, DROP STATISTICS, etc.

## Public surface

- `RemoveObjects` — entry from utility. Loops over the `DropStmt.objects` list, resolves each name to an `ObjectAddress` (via `get_object_address`), accumulates into `ObjectAddresses`, then calls `performMultipleDeletions` (catalog/dependency.c). The dependency framework figures out cascade vs restrict.
- `does_not_exist_skipping` — emit the right "X does not exist, skipping" NOTICE when `IF EXISTS` matches a missing object.
- `owningrel_does_not_exist_skipping`, `schema_does_not_exist_skipping`, `type_in_list_does_not_exist_skipping` — IF EXISTS variants that need to distinguish "schema missing" from "object in schema missing" from "owning relation missing".

## IF EXISTS subtlety

`DROP TYPE IF EXISTS foo.bar` could mean (a) schema foo doesn't exist, (b) schema foo exists but type bar doesn't. Both must downgrade to NOTICE, not ERROR. The various `*_does_not_exist_skipping` helpers exist to detect which case we're in so the NOTICE wording is right.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`
