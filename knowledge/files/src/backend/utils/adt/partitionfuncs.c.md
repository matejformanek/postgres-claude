# src/backend/utils/adt/partitionfuncs.c

## Purpose

SQL helpers for navigating a partitioned-table inheritance tree:
`pg_partition_tree(rootrelid)`, `pg_partition_root(relid)`, and
`pg_partition_ancestors(relid)`.

## Role in PG

Read-only metadata views over `pg_class` / `pg_inherits`. Used by tools
(psql `\dP`, monitoring) and by user queries. Returns NULL/empty for
non-partition input rather than erroring (`partitionfuncs.c:33-51`).

## Key functions

- `check_rel_can_be_partition(relid)` (`:33-51`) — static gate:
  relation exists, is either a partition (`relispartition`) or itself
  has partitions (`RELKIND_HAS_PARTITIONS(relkind)`).
- `pg_partition_tree(rootrelid)` (`:61-154`) — SRF returning `(relid,
  parentid, isleaf, level)`. Implementation: `find_all_inheritors(rootrelid,
  AccessShareLock, NULL)` (note: locks every descendant under
  `AccessShareLock` for the duration), then per row computes
  `get_partition_ancestors(relid)` to derive parent + level (`:114`).
- `pg_partition_root(relid)` (`:163-192`) — returns top-most ancestor
  or `relid` itself if root; `PG_RETURN_NULL()` if not a partition tree
  member.
- `pg_partition_ancestors(relid)` (`:200-238`) — SRF returning the
  ancestor chain *including* the input relation itself, ordered
  child→root (via `lcons_oid(relid, ancestors)` on `:219`).

## State / globals

None.

## Phase D notes

- **AccessShareLock on every partition**:
  `find_all_inheritors(rootrelid, AccessShareLock, NULL)` (`:88`)
  locks the entire tree. Calling `pg_partition_tree(huge_root)`
  from a low-priv role grabs `AccessShareLock` on every leaf — won't
  block writers but does occupy lock table slots. Potential mild
  DoS / lock-table-pressure surface on very wide partition hierarchies
  (10k+ leaves).
- **Visibility is whatever pg_class/pg_inherits give you**: no
  ACL filtering. A role with USAGE on a schema sees the whole tree under
  it. If a partition root is in a schema the caller can see but a leaf
  is in a schema they cannot, `pg_partition_tree` still emits the OID
  (info disclosure for partitions hidden by ACL).
- **Quadratic-ish work**: per-leaf `get_partition_ancestors(relid)`
  call inside the SRF loop (`:114`) — O(leaves × depth). Cheap in
  practice but worth noting.

## Potential issues

- [ISSUE-info-disclosure: leaf OIDs returned even when the caller has
  no privilege to see / SELECT from those leaves. They get a relid,
  not data, but enumeration is still leakage (low)]
- [ISSUE-dos: `find_all_inheritors` lock acquisition on huge trees;
  no nrows clamp (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
