# dependency.h

- **Source path:** `source/src/include/catalog/dependency.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support inter-object dependencies."

## Key declarations

- `DependencyType` enum — character literals matching pg_depend.deptype: `DEPENDENCY_NORMAL` 'n', `DEPENDENCY_AUTO` 'a', `DEPENDENCY_INTERNAL` 'i', `DEPENDENCY_EXTENSION` 'e', `DEPENDENCY_AUTO_EXTENSION` 'x', `DEPENDENCY_PARTITION_PRI` 'P', `DEPENDENCY_PARTITION_SEC` 'S'. **The character is the on-disk value** — changing the letter is an on-disk format break.
- `ObjectClass` enum (now mostly superseded by the ObjectProperty table in objectaddress.c).
- `ObjectAddresses` opaque struct.
- API prototypes: `performDeletion`, `performMultipleDeletions`, `recordDependencyOn`, `recordMultipleDependencies`, `recordDependencyOnExpr`, `recordDependencyOnSingleRelExpr`, `recordDependencyOnCurrentExtension`, `recordPinnedDependency`, `AcquireDeletionLock` / `ReleaseDeletionLock`.
- `DropBehavior` enum: DROP_RESTRICT, DROP_CASCADE.
- `PERFORM_DELETION_*` flag bits passed to `performDeletion`.

## Tally

`[verified-by-code]=2 [from-comment]=1`
