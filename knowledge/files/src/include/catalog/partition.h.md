# partition.h

- **Source path:** `source/src/include/catalog/partition.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Header for `partition.c`. Pulls in `partitioning/partdefs.h` (the runtime partition descriptor types) and declares the catalog-side helpers.

## Surface

`get_partition_parent`, `get_partition_ancestors`, `index_get_partition`, `map_partition_varattnos`, `has_partition_attrs`, `get_default_partition_oid`, `update_default_partition_oid`, `get_proposed_default_constraint`. See `partition.c.md`.

## Tally

`[verified-by-code]=1`
