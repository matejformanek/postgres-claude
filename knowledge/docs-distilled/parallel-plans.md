---
source_url: https://www.postgresql.org/docs/current/parallel-plans.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Parallel Plans (parallel-query ch. 15.3)

The plan-node catalog leaf of §15 — *which executor nodes can go parallel and
under what rule.* The parent `parallel-query.md` folded in §15.1
(how-parallel-query-works) and §15.4 (parallel-safety) but **not** this §15.3
node taxonomy. Pairs with the `parallel-query` and `executor-and-planner`
skills and the `parallel-*` idioms.

## The core requirement

- **Every parallel plan is built around partial plans:** each worker must
  produce a *subset* of output rows such that each required row is produced by
  exactly one process. The driving (lowest) table almost always uses a
  parallel-aware scan; everything above must preserve the "each row once"
  invariant. [from-docs]
- **The leader participates**, and `Gather` / `Gather Merge` are the nodes that
  collect partial results into the leader (`Gather Merge` preserves sort order;
  `Gather` does not). [from-docs]

## §15.3.1 Parallel scans (three kinds)

- **Parallel Sequential Scan** — blocks are divided into ranges handed out to
  workers; a worker finishes its range, then requests the next. Block-granularity
  work distribution. [from-docs]
- **Parallel Bitmap Heap Scan** — *one leader* scans the index(es) and builds the
  bitmap; the heap blocks are then divided like a parallel seqscan. **The heap
  scan is parallel; the underlying index scan is not.** [from-docs]
- **Parallel Index / Index-Only Scan** — workers take turns: each claims a single
  index block and returns all tuples it references while others read different
  blocks. **btree only.** Each worker's output is sorted within that worker.
  [from-docs]

## §15.3.2 Parallel joins (inner-side rule is the crux)

- **Nested loop** — inner side is **always non-parallel, executed in full** per
  worker; efficient when the inner is an index scan (outer tuples + lookups split
  across workers). [from-docs]
- **Merge join** — inner side **always non-parallel, executed in full**; often
  inefficient because the inner work (and any sort) is *duplicated in every
  worker*. [from-docs]
- **Standard hash join** — every worker builds an *identical full copy* of the
  hash table from the inner side; wasteful when the table is large. [from-docs]
- **Parallel Hash Join** — uses a *parallel hash*: the inner-side build of a
  **single shared hash table** is divided across workers. The win over standard
  hash join. [from-docs]

## §15.3.3 Parallel aggregation (two-stage)

- **Stage 1 `Partial Aggregate`** — each worker aggregates its slice into a
  partial per-group result. [from-docs]
- **Stage 2 `Finalize Aggregate`** — partials flow up through `Gather`/`Gather
  Merge` to the leader, which combines them per group. [from-docs]
- **Planner caution:** worst case the `Finalize Aggregate` sees as many groups as
  total input rows, so high-cardinality grouping looks unfavorable and the
  planner usually declines parallel aggregation there. [from-docs]
- **Not supported when** any aggregate is parallel-unsafe or lacks a *combine
  function*; or has an `internal` transition state without serialize/deserialize
  functions; or the aggregate carries `DISTINCT` / `ORDER BY`; or it is an
  ordered-set aggregate; or the query uses `GROUPING SETS`; or not all joins are
  inside the parallel portion. [from-docs]

## §15.3.4 Parallel Append

- A `Parallel Append` spreads workers *across* child plans so multiple children
  run simultaneously (vs. a plain `Append` in a parallel plan, where all workers
  cooperate on one child at a time, in order). [from-docs]
- **Unique to `Parallel Append`: it can mix partial and non-partial children.** A
  non-partial child is scanned by exactly one process (scanning it more than once
  would duplicate rows). This yields coarse-grained parallelism even when no
  efficient partial plan exists — e.g. a partitioned scan over an index type that
  has no parallel scan: a `Parallel Append` of plain `Index Scan`s, each run to
  completion by one worker, different scans concurrent. [from-docs]
- Toggled by `enable_parallel_append`. [from-docs]

## §15.3.5 Tips

- To coax a missing parallel plan: lower `parallel_setup_cost` and
  `parallel_tuple_cost` (even 0 may not suffice if other constraints bind).
  Diagnose non-parallelization via §15.2 / §15.4. Use `EXPLAIN (ANALYZE,
  VERBOSE)` for per-worker node stats to spot skew. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/parallel-query.md]] — parent chapter (§15.1/§15.4).
- [[knowledge/idioms/parallel-hash-join.md]] — the shared-hash build behind
  Parallel Hash Join.
- [[knowledge/idioms/parallel-bitmap-heap.md]] — the leader-builds-bitmap /
  workers-split-heap pattern above.
- [[knowledge/idioms/parallel-gather-merge.md]] — `Gather Merge` order-preserving
  collection.
- [[knowledge/idioms/aggregate-partial-finalize.md]] — the Partial/Finalize
  combine-function machinery §15.3.3 depends on.
- [[knowledge/idioms/parallel-context-and-dsm.md]] / [[knowledge/idioms/parallel-worker-coordination.md]]
  — the DSM/worker plumbing under all of these nodes.
- [[knowledge/subsystems/executor.md]] — node dispatch for Gather/GatherMerge.

## Open questions

- Map each node name here to its `nodeGather.c` / `nodeGatherMerge.c` /
  `nodeHash.c` (Parallel Hash) / `nodeAppend.c` site at anchor `ab3023ad1e68` on
  a future executor deep read.
