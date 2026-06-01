# partition.c

- **Source path:** `source/src/backend/catalog/partition.c`
- **Lines:** ~390
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Partitioning related data structures and functions." Helper layer: walk pg_inherits/pg_class to answer "who is my partition parent / ancestors / default", remap attribute numbers across the parent/child schema, derive the default-partition's check constraint. The heavy lifting of partition bound storage is `catalog/pg_partitioned_table.h` rows written via `StorePartitionKey`/`StorePartitionBound` in heap.c; the tuple-routing dispatch table is in `partitioning/partbounds.c`.

## Public surface

- `get_partition_parent` (53) — return parent relid; `even_if_detached` controls whether a detach-pending partition still reports its parent.
- `get_partition_parent_worker` (85) — the actual pg_inherits scan (looking for the `inhrelid = relid AND inhseqno = 1` row).
- `get_partition_ancestors` (134) — full ancestor chain to root.
- `index_get_partition` (176) — given a partition Relation and a parent's index OID, find the partition's matching index OID (via pg_inherits on the index OIDs).
- `map_partition_varattnos` (222) — rewrite a parent's expression tree to use child-schema attnums.
- `has_partition_attrs` (255) — predicate: does this set of attnums overlap the partition key (used by ALTER COLUMN to refuse type changes / drops that would break partitioning).
- `get_default_partition_oid` (315), `update_default_partition_oid` (340) — find / set the default partition (stored on pg_partitioned_table.partdefid).
- `get_proposed_default_constraint` (370) — for "what would the default partition's CHECK constraint look like after adding this new partition" — used to validate that the default isn't violated.

## Confidence tag tally

`[verified-by-code]=4`
