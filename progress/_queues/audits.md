# Queue: pg-quality-auditor — audit (long-form doc) side

Format: `[status] <doc-path> verified=<YYYY-MM-DD|never> [reason=<tag>]`
Refill rule: re-walk `knowledge/{architecture,subsystems,idioms,data-structures}/*.md`;
any doc whose `verified` annotation is > 30 days old (or `never`) goes
back to `[pending]`.

**Added 2026-06-12 (pg-anchor-refresh):** `pg-anchor-refresh` (11th routine,
schedule 03:37) also enqueues `knowledge/files/<path>.md` entries with
`reason=anchor-bump <old>..<new>` whenever upstream master moves and the
touched paths have an existing per-file doc. These are higher-priority
than the periodic 30-day refresh: process them first.

## Entries

[pending] knowledge/subsystems/foreign.md verified=2026-06-10
[pending] knowledge/subsystems/libpq-backend.md verified=2026-06-10
[pending] knowledge/subsystems/headers-wave3.md verified=2026-06-10
[pending] knowledge/subsystems/main.md verified=2026-06-10
[pending] knowledge/subsystems/port.md verified=2026-06-10
[pending] knowledge/idioms/locking-overview.md verified=2026-06-11
[pending] knowledge/idioms/memory-contexts.md verified=2026-06-11
[pending] knowledge/idioms/catalog-conventions.md verified=2026-06-11
[pending] knowledge/idioms/error-handling.md verified=2026-06-11
[pending] knowledge/idioms/fmgr.md verified=2026-06-11
[pending] knowledge/idioms/spi.md verified=2026-06-11
[pending] knowledge/data-structures/bufferdesc-state.md verified=2026-06-11
[pending] knowledge/idioms/parser-pipeline.md verified=2026-06-12
[pending] knowledge/idioms/node-types-and-lists.md verified=2026-06-12
[pending] knowledge/idioms/bgworker-and-parallel.md verified=2026-06-12
[pending] knowledge/idioms/guc-variables.md verified=2026-06-12
[pending] knowledge/data-structures/heap-tuple-layout.md verified=2026-06-12
[pending] knowledge/data-structures/pgproc-fields.md verified=2026-06-12
[pending] knowledge/architecture/mvcc.md verified=2026-06-13
[pending] knowledge/architecture/wal.md verified=2026-06-13
[pending] knowledge/architecture/planner.md verified=2026-06-13
[pending] knowledge/architecture/query-lifecycle.md verified=2026-06-13
[pending] knowledge/data-structures/snapshot-lifecycle.md verified=2026-06-13 [drift-fixed: heapam_visibility.c cite 177-191→13-35]
[pending] knowledge/architecture/executor.md verified=2026-06-13 [drift-fixed: nodeModifyTable.c §8a cites +13 lines]
[pending] knowledge/architecture/overview.md verified=2026-06-14
[pending] knowledge/architecture/access-methods.md verified=2026-06-14
[pending] knowledge/architecture/process-model.md verified=2026-06-14
[pending] knowledge/architecture/replication.md verified=2026-06-14
[pending] knowledge/subsystems/access-heap.md verified=2026-06-14
[pending] knowledge/subsystems/access-transam.md verified=2026-06-14
[pending] knowledge/subsystems/executor.md verified=2026-06-14 [drift-fixed: execExpr.c §3.1/§3.2 cites −20/−33 + phantom ExecInitExprWithContext removed; nodeModifyTable.c §9 cites −13]
[pending] knowledge/subsystems/storage-ipc.md verified=2026-06-15
[pending] knowledge/subsystems/storage-lmgr.md verified=2026-06-15
[pending] knowledge/subsystems/utils-cache.md verified=2026-06-15
[pending] knowledge/subsystems/utils-mmgr.md verified=2026-06-15
[pending] knowledge/subsystems/storage-buffer.md verified=2026-06-15
[pending] knowledge/subsystems/jit.md verified=2026-06-15
[pending] knowledge/subsystems/optimizer.md verified=2026-06-15 [drift-fixed: subselect.c SS_process_ctes 883→886, SS_process_sublinks 2206→2209]
[pending] knowledge/subsystems/partitioning.md verified=2026-06-15 [drift-fixed: PartitionRangeBound 50-71→65-71, partition_hbound_cmp 3770-3778→3580-3588]

## anchor-bump (2026-06-14) — e18b0cb7344..da1eff08a5be (20 commits)

[pending] knowledge/files/contrib/seg/seg.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/contrib/xml2/xpath.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/access/transam/xlog.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/access/transam/xlogutils.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/catalog/pg_subscription.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/commands/subscriptioncmds.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/commands/tablecmds.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/libpq/crypt.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/libpq/pqmq.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/nodes/makefuncs.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/parser/parse_coerce.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/parser/parse_expr.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/parser/parse_func.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/parser/parse_relation.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/parser/parse_target.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/replication/logical/relation.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/replication/walsender.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/utils/adt/ri_triggers.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/utils/adt/xml.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/utils/cache/inval.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/utils/init/postinit.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/bin/psql/describe.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/include/miscadmin.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/include/parser/parse_relation.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/subsystems/parser-and-rewrite.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be (6 impacted parser files)
[pending] knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md  reason=anchor-bump 2026-06-15:da1eff08a5be..b78cd2bda5b1
