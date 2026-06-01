# tupconvert.c

- **Source path:** `source/src/backend/access/common/tupconvert.c`
- **Lines:** 309
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tupconvert.h`, `attmap.c` (builds the mapping), `executor/execPartition.c`, `commands/copyfrom.c`, `replication/logical/relation.c`.

## Purpose

Convert a tuple from one TupleDesc to a logically-equivalent but differently-ordered TupleDesc. Common when: tuple-routing into a partition, inheritance parent ↔ child, COPY FROM into a partitioned table, logical-replication apply when the subscriber's table column order differs from the publisher's. The actual reordering is driven by an `AttrMap` from `attmap.c`. [from-comment, tupconvert.c:1-19]

## Top-of-file comment

> "Tuple conversion support. These functions provide conversion between rowtypes that are logically equivalent but might have columns in a different order or different sets of dropped columns." [from-comment, tupconvert.c:3-9]

## Public surface

- `convert_tuples_by_position` (60) — Build a `TupleConversionMap` matching by position; returns NULL if already physically compatible.
- `convert_tuples_by_name` (103) — Build by-name; returns NULL if no conversion needed.
- `convert_tuples_by_name_attrmap` (125) — Already have an `AttrMap`; just wrap it with workspace arrays.
- `execute_attr_map_tuple` (155) — Apply the map to a `HeapTuple`, producing a new HeapTuple.
- `execute_attr_map_slot` (193) — Apply to a `TupleTableSlot` (executor preferred form; cheaper because it works on the deformed values).
- `execute_attr_map_cols` (253) — Apply to a `Bitmapset` of attribute numbers (used to translate which-columns-changed bitmaps across rowtypes — e.g. logical replication).
- `free_conversion_map` (300).

## Key invariants

- All three `convert_tuples_by_*` setup routines return NULL when source and destination are physically congruent (same natts, same per-attribute typid/typmod, dropped columns aligned). Callers MUST check for NULL — it is the explicit signal "no conversion needed". [from-comment, tupconvert.c:26-40; verified-by-code]
- The TupleConversionMap holds POINTERS to the input/output TupleDescs — those must outlive the map (callers usually own both descriptors). [from-comment, tupconvert.c:36-37]
- The map's `attrMap[i]` is a 1-based input attnum (0 = "produce NULL", for dropped output columns). [from-comment, tupconvert.c:46-52]
- `execute_attr_map_tuple` palloc's the new tuple in the current memory context; `execute_attr_map_slot` writes into the destination slot in-place. [verified-by-code]

## Functions of note

1. **`convert_tuples_by_position`** (60) — Walk both descriptors skipping dropped columns; on each non-dropped pair check typid+typmod match; reject with `ERROR` (`ERRCODE_DATATYPE_MISMATCH`) on mismatch. Build `AttrMap` via `build_attrmap_by_position`. [verified-by-code]
2. **`convert_tuples_by_name`** (103) — Delegates to `build_attrmap_by_name_if_req` (returns NULL for the common no-op case), then constructs workspace arrays. [verified-by-code]
3. **`execute_attr_map_slot`** (193) — `slot_getallattrs(in_slot)`, then for each output i: if `attrMap[i] != 0` copy values/isnull from input slot; else mark NULL. Calls `ExecStoreVirtualTuple(out_slot)`. [verified-by-code]
4. **`execute_attr_map_cols`** (253) — Translates a `Bitmapset` of input attnums to a `Bitmapset` of output attnums by inverting the map. Used by logical replication and trigger code that tracks "modified columns". [verified-by-code]

## Cross-references

- Built by: `attmap.c`'s `build_attrmap_by_*` helpers.
- Consumed by: `execPartition.c::ExecInitPartitionInfo` (tuple-routing), `copyfrom.c` (partitioned COPY), logical-replication apply, foreign-table imports, ALTER TABLE inheritance changes.

## Confidence tag tally
`[verified-by-code]=5 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=0`
