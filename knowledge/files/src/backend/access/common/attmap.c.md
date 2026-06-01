# attmap.c

- **Source path:** `source/src/backend/access/common/attmap.c`
- **Lines:** 329
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `attmap.h`, `tupconvert.c` (consumer), `commands/tablecmds.c` (ALTER TABLE INHERIT, partition attach).

## Purpose

Build and manage `AttrMap`: a mapping from output-column attnum → input-column attnum, used whenever two logically equivalent rowtypes have columns in different orders (partition vs. parent, child vs. parent, foreign-table import). Most commonly fed into `tupconvert.c::convert_tuples_by_name_attrmap`. [from-comment, attmap.c:5-15]

## Top-of-file comment

> "Attribute mapping support. This file provides utility routines to build and manage attribute mappings by comparing input and output TupleDescs. Such mappings are typically used by DDL operating on inheritance and partition trees to do a conversion between rowtypes logically equivalent but with columns in a different order, taking into account dropped columns. They are also used by the tuple conversion routines in tupconvert.c." [from-comment, attmap.c:3-15]

## Public surface

- `make_attrmap` (40) — Allocate a fresh `AttrMap` with `maplen` entries (zeroed).
- `free_attrmap` (56) — pfree the entries and the struct.
- `build_attrmap_by_position` (75) — Match columns by position; dropped columns are skipped on both sides; type/typmod must match for non-dropped pairs (or throws `ERROR`).
- `build_attrmap_by_name` (175) — Match columns by name; case-sensitive; throws on missing input column (unless the output column is dropped).
- `build_attrmap_by_name_if_req` (261) — Same as by-name but returns NULL if no mapping is actually needed (a fast-path for partition tuple-routing).

## Key invariants

- A zero entry in `attnums[i]` means "output column i is dropped" (or no input column maps to it); the conversion code substitutes NULL. [verified-by-code, attmap.c:39-48; consumed by tupconvert.c]
- `build_attrmap_by_position` enforces type identity (atttypid + atttypmod) on every non-dropped pair. Mismatch is `ereport(ERROR, ERRCODE_DATATYPE_MISMATCH)`. [verified-by-code, attmap.c:75-174]
- `build_attrmap_by_name_if_req` returning NULL means the descriptors are physically congruent — callers MUST handle NULL (means "no conversion needed"). [verified-by-code, attmap.c:261-287]
- `check_attrmap_match` (static, 288) — sanity check: for every output column, either input attnum is valid and types match, or output is dropped. Used as the "no-op detection" by `build_attrmap_by_name_if_req`. [verified-by-code]

## Cross-references

- Producers: `tablecmds.c` (ATTACH PARTITION, INHERIT), `partition.c`, `postgres_fdw`, logical-replication apply worker.
- Consumers: `tupconvert.c`, `execPartition.c` (tuple-routing).

## Confidence tag tally
`[verified-by-code]=5 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
