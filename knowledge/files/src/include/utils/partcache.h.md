# partcache.h

- **Source path:** `source/src/include/utils/partcache.h`
- **Lines:** 103
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `partcache.c` (impl), `partitioning/partdefs.h` (forward-decl of `PartitionKey`).

## Purpose

Defines `PartitionKeyData` and the public `Relation*Partition*` accessors plus a set of static-inline column-level inquiry helpers.

## Top-of-file comment

Just identification; no substantive comment.

## Public surface

- **Type**: `PartitionKeyData` (25). `PartitionKey` is a typedef-pointer in `partitioning/partdefs.h`.
- **Functions**: `RelationGetPartitionKey(Relation) → PartitionKey`, `RelationGetPartitionQual(Relation) → List *`, `get_partition_qual_relid(Oid) → Expr *`.
- **Inline accessors**: `get_partition_strategy`, `get_partition_natts`, `get_partition_exprs`, `get_partition_col_attnum`, `get_partition_col_typid`, `get_partition_col_typmod`, `get_partition_col_collation`.

## Key types

- **`PartitionKeyData`** (25) — `strategy`, `partnatts`, `partattrs` (AttrNumbers, 0 = expression), `partexprs` (parallel list filling 0 slots), `partopfamily`/`partopcintype`/`partsupfunc` per column, `partcollation`, plus pre-cached type info `parttypid`/`parttypmod`/`parttyplen`/`parttypbyval`/`parttypalign`/`parttypcoll` (so callers don't need to re-look-up per column).

## Confidence tag tally

verified-by-code: 1 — from-comment: 0 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-cache.md](../../../../subsystems/utils-cache.md)
