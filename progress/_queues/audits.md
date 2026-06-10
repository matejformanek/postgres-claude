# Queue: pg-quality-auditor — audit (long-form doc) side

Format: `[status] <doc-path> verified=<YYYY-MM-DD|never>`
Refill rule: re-walk `knowledge/{architecture,subsystems,idioms,data-structures}/*.md`;
any doc whose `verified` annotation is > 30 days old (or `never`) goes
back to `[pending]`.

## Entries

[pending] knowledge/idioms/locking-overview.md verified=never
[pending] knowledge/idioms/memory-contexts.md verified=never
[pending] knowledge/idioms/catalog-conventions.md verified=never
[pending] knowledge/idioms/error-handling.md verified=never
[pending] knowledge/idioms/fmgr.md verified=never
[pending] knowledge/idioms/spi.md verified=never
[pending] knowledge/idioms/parser-pipeline.md verified=never
[pending] knowledge/idioms/node-types-and-lists.md verified=never
[pending] knowledge/idioms/bgworker-and-parallel.md verified=never
[pending] knowledge/idioms/guc-variables.md verified=never
[pending] knowledge/data-structures/bufferdesc-state.md verified=never
[pending] knowledge/data-structures/heap-tuple-layout.md verified=never
[pending] knowledge/data-structures/pgproc-fields.md verified=never
[pending] knowledge/data-structures/snapshot-lifecycle.md verified=never
[pending] knowledge/architecture/overview.md verified=2026-06-04
[pending] knowledge/architecture/mvcc.md verified=2026-06-04
[pending] knowledge/architecture/wal.md verified=2026-06-04
[pending] knowledge/architecture/executor.md verified=2026-06-04
[pending] knowledge/architecture/planner.md verified=2026-06-04
[pending] knowledge/architecture/query-lifecycle.md verified=2026-06-04
[pending] knowledge/architecture/access-methods.md verified=2026-06-04
[pending] knowledge/architecture/process-model.md verified=2026-06-04
[pending] knowledge/architecture/replication.md verified=2026-06-07
[pending] knowledge/subsystems/access-heap.md verified=2026-06-07
[pending] knowledge/subsystems/access-transam.md verified=2026-06-07
[pending] knowledge/subsystems/executor.md verified=2026-06-07
[pending] knowledge/subsystems/optimizer.md verified=2026-06-07
[pending] knowledge/subsystems/storage-buffer.md verified=2026-06-08
[pending] knowledge/subsystems/storage-ipc.md verified=2026-06-08
[pending] knowledge/subsystems/storage-lmgr.md verified=2026-06-08
[pending] knowledge/subsystems/utils-cache.md verified=2026-06-08
[pending] knowledge/subsystems/utils-mmgr.md verified=2026-06-08
[pending] knowledge/subsystems/partitioning.md verified=2026-06-10
[pending] knowledge/subsystems/jit.md verified=2026-06-10
[pending] knowledge/subsystems/foreign.md verified=2026-06-10
[pending] knowledge/subsystems/libpq-backend.md verified=2026-06-10
[pending] knowledge/subsystems/headers-wave3.md verified=2026-06-10
[pending] knowledge/subsystems/main.md verified=2026-06-10
[pending] knowledge/subsystems/port.md verified=2026-06-10
