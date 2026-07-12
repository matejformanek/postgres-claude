---
source_url: https://www.postgresql.org/docs/current/ddl-partitioning.html
fetched_at: 2026-07-11T19:54:35Z
anchor_sha: 54cd6fc83176d7c03abf95554aef26b0b24acc7d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "5.12 Table Partitioning"
---

# Docs distilled — Declarative Partitioning (ddl-partitioning)

The RANGE/LIST/HASH declarative-partitioning subsystem: a partitioned parent is
a storage-less router; partitions are ordinary tables; the planner/executor
prune partitions in two phases. Maps onto the executor's tuple-routing
(`execPartition.c`) and the optimizer's inheritance expansion (`inherit.c`).

## Non-obvious claims

- **The partitioned table has *no storage of its own* — it is a "virtual"
  table.** "the storage belongs to *partitions*, which are otherwise-ordinary
  tables". This is a distinct `relkind`: `RELKIND_PARTITIONED_TABLE = 'p'`
  (vs. `'r'` for an ordinary heap). [from-docs] + [verified-by-code]
  `src/include/catalog/pg_class.h:179`.
- **Three strategies, distinct bound semantics.** RANGE bounds are "inclusive
  at the lower end and exclusive at the upper end" (so a value equal to the
  upper bound belongs to the *next* partition); LIST enumerates key values;
  HASH assigns by `(modulus, remainder)` on the hash of the partition key.
  [from-docs]
- **Tuple routing is an executor operation.** Rows inserted into the parent are
  routed to the correct partition by `ExecFindPartition`; updating a row's
  partition key can *move* the row to a different partition. Inserting a row
  that maps to no existing partition is an error unless a DEFAULT partition
  exists. [from-docs] + [verified-by-code]
  `src/backend/executor/execPartition.c:268` (`ExecFindPartition`).
- **Partition bound → implicit CHECK constraint, created automatically.** You do
  not hand-write the boundary CHECK; the system synthesizes the partition
  constraint. [from-docs]
- **`ATTACH PARTITION` full-scans the table under `ACCESS EXCLUSIVE` to validate
  the bound** — unless a matching `CHECK` constraint already proves the data
  fits, in which case the scan is skipped (recommended pattern: add the CHECK,
  attach, drop the now-redundant CHECK). Sub-partitions are recursively locked
  and scanned until a suitable CHECK or a leaf is reached. [from-docs]
- **`DETACH PARTITION CONCURRENTLY` downgrades the lock** from `ACCESS
  EXCLUSIVE` (plain DETACH) to `SHARE UPDATE EXCLUSIVE`, at the cost of extra
  restrictions. [from-docs]
- **Partition pruning is a two-phase optimization, driven by bounds not
  indexes.** Plan-time pruning removes partitions whose bounds can't satisfy the
  `WHERE` clause (these never appear in `EXPLAIN`; count them via "Subplans
  Removed"). Execution-time pruning removes partitions using values known only
  at runtime — subquery results and execution-time parameters (e.g.
  parameterized nested-loop joins) — and re-runs whenever such a parameter
  changes. Controlled by `enable_partition_pruning` (default on). [from-docs]
- **Plan-time-pruned partitions are still *locked* at the start of execution**,
  even though they are removed from the plan. Pruning reduces scan work, not the
  lock footprint. [from-docs]
- **Pruning uses partition bounds; constraint exclusion uses CHECK
  constraints.** They are near-identical techniques, but `constraint_exclusion`
  (default `partition`) is the legacy-inheritance path, only fires at plan time,
  and only with constant/parameter `WHERE` clauses (a non-immutable
  `CURRENT_TIMESTAMP` comparison can't be excluded). [from-docs] +
  [verified-by-code] the `partition` default maps to
  `CONSTRAINT_EXCLUSION_PARTITION` at
  `src/backend/utils/misc/guc_tables.c:329`.
- **Indexes/constraints on the parent are also "virtual" and cascade.** An index
  or unique constraint declared on the partitioned table has no data of its own;
  the real indexes live on the partitions, and new/attached partitions inherit
  matching indexes. A concurrent-safe workaround exists: `CREATE INDEX ON ONLY
  parent`, build each child index `CONCURRENTLY`, then `ALTER INDEX … ATTACH
  PARTITION`. [from-docs]
- **Uniqueness/exclusion limitations stem from per-partition index enforcement.**
  A unique or primary-key constraint must include *all* partition-key columns
  (and the key may not use expressions), because "the individual indexes making
  up the constraint can only directly enforce uniqueness within their own
  partitions". Exclusion constraints likewise must include every partition-key
  column and compare them for equality. [from-docs]
- **`CHECK` and `NOT NULL` on a partitioned table are always inherited** by all
  partitions — `NO INHERIT` variants are disallowed. Partitions may not add
  columns absent from the parent, and temp/permanent relations can't mix in one
  partition tree. `BEFORE ROW` INSERT triggers cannot redirect a row to a
  different destination partition. [from-docs]
- **Partition count is a planner-cost tradeoff, not free.** "The query planner
  is generally able to handle partition hierarchies with up to a few thousand
  partitions" *provided* pruning eliminates most of them; each touched partition
  loads metadata into every session's local memory, and too many partitions
  inflate planning time + memory. [from-docs]

> Cross-ref: `enable_partitionwise_join` / `enable_partitionwise_aggregate` are
> not described on this page — they live in `runtime-config-query` (already
> distilled).

## Links into corpus

- [[knowledge/files/src/backend/executor/execPartition.c.md]] — `ExecFindPartition`
  tuple routing + the partition-routing ResultRelInfo cache.
- [[knowledge/files/src/backend/optimizer/util/inherit.c.md]] — how a
  partitioned parent RTE is expanded into an append over partitions
  (`expand_partitioned_rtentry`).
- [[knowledge/subsystems/executor.md]] — ModifyTable / tuple routing home.
- [[knowledge/subsystems/optimizer.md]] — where plan-time pruning + append
  expansion happen.
- [[knowledge/docs-distilled/using-explain.md]] — reading "Subplans Removed" and
  pruned-partition EXPLAIN output.
- [[knowledge/docs-distilled/runtime-config-query.md]] —
  `enable_partition_pruning`, `constraint_exclusion`,
  `enable_partitionwise_*` GUC defaults.
- [[knowledge/docs-distilled/ddl-inherit.md]] — the legacy-inheritance mechanism
  declarative partitioning is built on top of.
