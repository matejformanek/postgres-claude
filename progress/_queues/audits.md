# Queue: pg-quality-auditor — audit (long-form doc) side

Format: `[status] <doc-path> verified=<YYYY-MM-DD|never>`
Refill rule: re-walk `knowledge/{architecture,subsystems,idioms,data-structures}/*.md`;
any doc whose `verified` annotation is > 30 days old (or `never`) goes
back to `[pending]`.

## Entries

[pending] knowledge/architecture/overview.md verified=never
[pending] knowledge/architecture/mvcc.md verified=never
[pending] knowledge/architecture/wal.md verified=never
[pending] knowledge/architecture/executor.md verified=never
[pending] knowledge/architecture/planner.md verified=never
[pending] knowledge/architecture/query-lifecycle.md verified=never
[pending] knowledge/architecture/access-methods.md verified=never
[pending] knowledge/architecture/process-model.md verified=never
[pending] knowledge/architecture/replication.md verified=never
[pending] knowledge/subsystems/access-heap.md verified=never
[pending] knowledge/subsystems/access-transam.md verified=never
[pending] knowledge/subsystems/executor.md verified=never
[pending] knowledge/subsystems/optimizer.md verified=never
[pending] knowledge/subsystems/storage-buffer.md verified=never
[pending] knowledge/subsystems/storage-ipc.md verified=never
[pending] knowledge/subsystems/storage-lmgr.md verified=never
[pending] knowledge/subsystems/utils-cache.md verified=never
[pending] knowledge/subsystems/utils-mmgr.md verified=never
[pending] knowledge/subsystems/partitioning.md verified=never
[pending] knowledge/subsystems/jit.md verified=never
[pending] knowledge/subsystems/foreign.md verified=never
[pending] knowledge/subsystems/libpq-backend.md verified=never
[pending] knowledge/subsystems/headers-wave3.md verified=never
[pending] knowledge/subsystems/main.md verified=never
[pending] knowledge/subsystems/port.md verified=never
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
