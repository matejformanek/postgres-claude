# pg_depend.c

- **Source path:** `source/src/backend/catalog/pg_depend.c`
- **Lines:** ~1 280
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_depend relation." Low-level CRUD for pg_depend rows. The graph **traversal** lives in dependency.c; this file writes/edits the rows. Plus some derived-info helpers (extension membership, sequence ownership, identity sequences, FK→index linkage).

## Public surface

- `recordDependencyOn` (51) — single-row insert: `(classId, objectId, refclassId, refobjectId, refobjsubId, deptype)`.
- `recordMultipleDependencies` (63) — batch: many `(classId, objectId)` → one referenced object, or vice versa.
- `recordDependencyOnCurrentExtension` (206) — if `creating_extension`, add an EXTENSION dep to the active CREATE EXTENSION's pg_extension row.
- `checkMembershipInCurrentExtension` (271) — extension scripts can't mention objects that already belong to a different extension.
- `deleteDependencyRecordsFor` (314), `deleteDependencyRecordsForClass` (364), `deleteDependencyRecordsForSpecific` (411) — delete-by-various-key, used during DROP and ALTER.
- `changeDependencyFor` (470), `changeDependenciesOf` (585), `changeDependenciesOn` (641) — re-target a dep when an object moves (ALTER ... OWNER TO, ALTER ... SET SCHEMA, REINDEX CONCURRENTLY swap).
- `isObjectPinned` (729) — implementation of `IsPinnedObject`: a row with refclassid=0 means "pinned, can't drop".
- `dependencyLockAndCheckObject` (752) — take the right lock then verify the object still exists.
- `getExtensionOfObject` (865) — find which extension owns an object (or InvalidOid if none).
- `getAutoExtensionsOfObject` (911) — all AUTO_EXTENSION deps.
- `getExtensionType` (963) — given an extension OID + type name, find the type if it's a member of that extension.
- `sequenceIsOwned` (1032), `getOwnedSequences_internal` (1081), `getOwnedSequences` (1140) — find sequences "owned" by a column (AUTO dep). Used by DROP COLUMN to cascade-drop the sequence.
- `getIdentitySequence` (1149) — find the IDENTITY sequence for a column.
- `get_index_constraint` (1192), `get_index_ref_constraints` (1248) — index ↔ constraint linkage via INTERNAL deps.

## Pinning

`recordPinnedDependencies` (called from initdb bootstrap, not this file) writes the refclassid=0 rows. After initdb completes, the bootstrap toggles off the pinning logic via `pg_stop_making_pinned_objects` (in catalog.c). Anything created post-initdb is **never** pinned; only the original bootstrap objects are immortal.

## Confidence tag tally

`[verified-by-code]=4 [inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
