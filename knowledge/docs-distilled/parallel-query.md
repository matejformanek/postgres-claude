---
source_url: https://www.postgresql.org/docs/current/parallel-query.html
also_fetched:
  - https://www.postgresql.org/docs/current/how-parallel-query-works.html
  - https://www.postgresql.org/docs/current/parallel-safety.html
fetched_at: 2026-06-03T19:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 15: Parallel Query

How PG splits one query across background workers. The two load-bearing
sub-pages are **15.1 How Parallel Query Works** and **15.4 Parallel Safety**;
15.2 (when usable) and 15.3 (plan shapes) are summarized.

## The execution model (15.1)

- **Gather / Gather Merge is the seam.** A `Gather` (or `Gather Merge`) node sits
  at the top of the parallel portion of the plan; it has **exactly one child**,
  and everything *below* it can run in workers. If Gather is the plan root the
  whole query is parallel; otherwise only the subtree is. [from-docs]
  [verified-by-code, source/src/backend/executor/execParallel.c — leader-side
  setup `ExecInitParallelPlan` at :653, via
  knowledge/files/src/backend/executor/execParallel.c.md]
- **The leader is also a worker.** The leader process does not just collect — it
  executes the parallel subplan itself. When the subplan emits *few* tuples the
  leader acts like an extra worker (speedup); when it emits *many*, the leader
  becomes saturated reading worker output and contributes little parallel work.
  [from-docs]
- **`Gather` destroys order; `Gather Merge` preserves it.** Plain `Gather` reads
  worker tuples in whatever order they arrive. `Gather Merge` requires each
  worker to produce *sorted* output and does an order-preserving k-way merge — the
  node you see above a parallel sort/index scan feeding an `ORDER BY`. [from-docs]
- **Three-level worker budget**, all must allow it:
  `max_parallel_workers_per_gather` (per-Gather planner cap) ≤
  `max_parallel_workers` (cluster parallel-query cap) ≤ `max_worker_processes`
  (the shared bgworker slot pool). A query **may launch fewer workers than
  planned, or zero**, if the pool is exhausted at run time — EXPLAIN shows
  `Workers Planned` vs `Workers Launched` precisely so you can spot the shortfall.
  [from-docs]
  [verified-by-code, via knowledge/idioms/bgworker-and-parallel.md — workers come
  from the same `RegisterDynamicBackgroundWorker` pool]
- **`dynamic_shared_memory_type` must not be `none`** — workers communicate via a
  DSM segment + `shm_mq` tuple queues, so DSM is a hard prerequisite. [from-docs]
  [verified-by-code, execParallel.c.md — "Create N shm_mq queues, one per worker"]

## When parallelism is *not* used (15.2, summarized)

A query is run serially if any of these hold: it writes data or locks rows
(`SELECT … FOR UPDATE/SHARE`); it calls a function marked `PARALLEL UNSAFE`; it
runs inside a query that is already parallel (no nesting); or it uses a cursor /
suspendable (`FETCH`-driven) execution. Raising `max_parallel_workers_per_gather`
to 0 disables parallelism globally. [from-docs]

## Parallel safety labeling (15.4)

The most consequential and error-prone part for extension/function authors.

- **Three labels**, set via `CREATE/ALTER FUNCTION … PARALLEL {SAFE|RESTRICTED|UNSAFE}`
  (also on `CREATE AGGREGATE`):
  - **PARALLEL SAFE** — may run anywhere, including inside a worker (below Gather).
  - **PARALLEL RESTRICTED** — may run in the *leader* during a parallel query but
    **never below Gather/Gather Merge**; its presence forces those operators to
    the leader but does not kill parallelism elsewhere.
  - **PARALLEL UNSAFE** — forces the *entire* query serial. [from-docs]
- **Default is PARALLEL UNSAFE.** Every user-defined function is unsafe until you
  declare otherwise — the conservative default, and the usual reason a custom
  function silently disables parallelism. [from-docs]
- **Mark UNSAFE if the function:** writes to the DB; changes transaction state
  (other than subtransactions for error recovery); accesses sequences (`nextval`);
  or makes persistent settings changes. [from-docs]
- **Mark RESTRICTED if the function:** touches temp tables, the client connection
  state, cursors, prepared statements, or backend-local state like
  `setseed`/`random`. [from-docs]
- **Always parallel-restricted plan elements** (independent of function labels):
  scans of CTEs, scans of temp tables, scans of foreign tables (unless the FDW
  implements `IsForeignScanParallelSafe`), and nodes referencing a correlated
  `SubPlan`. [from-docs]
- **Mislabeling is a footgun, not a soft hint:** a wrongly-SAFE function can give
  wrong answers or errors under parallel execution, and a mislabeled C function
  is undefined behavior. The label is a *promise the planner trusts*. [from-docs]

## Parallel-capable plan nodes (15.3, summarized)

Parallel Seq Scan, Parallel Bitmap Heap Scan, Parallel Index/Index-Only Scan,
Parallel (hash/nested-loop/merge) Join with a Parallel Hash, and Partial
Aggregate → Gather → Finalize Aggregate are the headline parallel-aware shapes.
The aggregate split (Partial in workers, Finalize in the leader) is why
`count(*)`/`sum()` parallelize cleanly while ordered-set aggregates often don't.
[from-docs]

## Links into corpus

- [[knowledge/idioms/bgworker-and-parallel.md]] — the parallel-worker idiom:
  ParallelContext, DSM, `shm_mq`, parallel-safe/restricted labeling from the
  C-code side.
- [[knowledge/files/src/backend/executor/execParallel.c.md]] — leader-side setup:
  `ExecInitParallelPlan` (`:653`), DSM serialization, queue creation, worker
  launch deferred to `ExecParallelCreateReaders`.
- [[knowledge/files/src/backend/access/transam/parallel.c.md]] — the generic
  parallel-worker infrastructure (entrypoint, state restore) Gather builds on.
- [[knowledge/architecture/executor.md]] — where Gather/Gather Merge sit in the
  ExecProcNode dispatch.
- Skill: `gucs-bgworker-parallel` — labeling functions parallel-safe, registering
  workers, parallel-query GUCs when writing C.

## Gaps / follow-ups

- The `runtime-config-resource` parallel GUCs (`min_parallel_table_scan_size`,
  `min_parallel_index_scan_size`, `parallel_setup_cost`, `parallel_tuple_cost`)
  govern *whether the planner bothers* — they live in the resource-config
  chapter, not here; worth seeding `runtime-config-resource` into the docs queue.
- `parallel_leader_participation` GUC (toggles the "leader is also a worker"
  behavior) is named in 15.1's surrounding text; confirm default `on` against
  guc_tables in a backfill run. [unverified]
</content>
