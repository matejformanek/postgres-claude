# pg_inherits.c

- **Source path:** `source/src/backend/catalog/pg_inherits.c`
- **Lines:** ~640
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/pg_inherits.h`, `commands/tablecmds.c` (ALTER TABLE ... INHERIT), `catalog/partition.c`.

## Purpose

"routines to support manipulation of the pg_inherits relation. Note: currently, this module mostly contains inquiry functions; actual creation and deletion of pg_inherits entries is mostly done in tablecmds.c. Perhaps someday that code should be moved here, but it'd have to be disentangled from other stuff such as pg_depend updates." [from-comment, pg_inherits.c:3-10]

## Public surface

- `find_inheritance_children` (59) — return List<Oid> of direct children of `parentrelId`, locking each at `lockmode`. Skips relations marked as detach-pending. [verified-by-code]
- `find_inheritance_children_extended` (83) — fuller version: `omit_detached` toggles whether detach-pending partitions are filtered, populates `*detached_exist` and `*detached_xmin` outputs. Critical observation: the detach visibility check uses the **active snapshot**, not the catalog snapshot, so the answer depends on whether the detacher's transaction looks committed to *this* query. [verified-by-code, pg_inherits.c:65-81]
- `find_all_inheritors` (256) — recursive: all direct + transitive descendants. Returns a flat List<Oid> in BFS order plus an optional parallel `numparents` list (how many distinct parents each entry has — relevant for diamond inheritance). Uses a `SeenRelsEntry` hash table for cycle/dup detection.
- `has_subclass` (356) — pg_class.relhassubclass shortcut (no scan).
- `has_superclass` (378) — scans pg_inherits for `inhrelid = relationId`.
- `typeInheritsFrom` (407) — composite-type inheritance check for the typed-table feature.
- `StoreSingleInheritance` (509) — insert one pg_inherits row `(inhrelid, inhparent, inhseqno, inhdetachpending=false)`.
- `DeleteInheritsTuple` (553) — remove a pg_inherits row; takes `expect_detach_pending` so callers can assert state.
- `PartitionHasPendingDetach` (621) — predicate over pg_inherits.inhdetachpending.

## Partitioning hook

Partitioning piggy-backs on pg_inherits: every partition has a pg_inherits row with `inhseqno=1` and `inhparent=<partitioned table OID>`. The same `find_inheritance_children` walks partition trees. The `inhdetachpending` flag is the **concurrent DETACH PARTITION** machinery: when DETACH ... CONCURRENTLY runs phase 1, it just sets this flag in pg_inherits; queries with old snapshots still see the partition, queries with new snapshots don't. Phase 2 (run from a later xact) actually deletes the pg_inherits row. [verified-by-code, pg_inherits.c:65-81]

## Confidence tag tally

`[verified-by-code]=5 [from-comment]=1`
