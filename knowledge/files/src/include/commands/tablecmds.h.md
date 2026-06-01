# tablecmds.h

- **Source path:** `source/src/include/commands/tablecmds.h`
- **Lines:** 111
- **Last verified commit:** `ef6a95c7c64`

Public surface of tablecmds.c. Forward-declares `AlterTableUtilityContext` (real def in tcop/utility.h) so the AT prototypes don't pull in utility.h. Declares `DefineRelation`, `RemoveRelations`, `ExecuteTruncate`, `ExecuteTruncateGuts`, `AlterTable`, `AlterTableInternal`, `AlterTableGetLockLevel`, the various `RangeVar_callbacks` used during name-resolution-under-lock (`RangeVarCallbackOwnsTable`, etc.), `RenameRelation`, `RenameRelationInternal`, `ResetRelRewrite`, `CheckTableNotInUse`, `BuildDescForRelation` (the columns-list → TupleDesc helper used by CREATE TABLE / composite types).
