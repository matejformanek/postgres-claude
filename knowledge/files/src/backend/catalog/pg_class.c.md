# pg_class.c

- **Source path:** `source/src/backend/catalog/pg_class.c`
- **Lines:** ~50
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Tiny stub. Just defines the `pg_class_aclmask` callback and friends here for layering reasons; the bulk of pg_class row writes lives in `heap.c` (`InsertPgClassTuple`, `AddNewRelationTuple`). Most fields of pg_class are updated by direct inplace-update calls scattered across the backend (VACUUM, ANALYZE, REINDEX).

## Confidence tag tally

`[inferred]=2`
