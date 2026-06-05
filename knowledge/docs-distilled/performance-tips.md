---
source_url: https://www.postgresql.org/docs/current/performance-tips.html
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
subsections_distilled:
  - https://www.postgresql.org/docs/current/using-explain.html
  - https://www.postgresql.org/docs/current/populate.html
note: >
  performance-tips.html is a chapter container (ToC only). This doc distills its
  two most internals-relevant subsections — Using EXPLAIN and Populating a
  Database. The chapter's statistics subsection is in
  knowledge/docs-distilled/planner-stats.md.
---

# Docs distilled — Chapter 14: Performance Tips (EXPLAIN + bulk load)

Two developer-facing skills from the Performance Tips chapter: reading an
`EXPLAIN` plan correctly (what the cost/rows/loops numbers actually mean), and
loading data fast (why `COPY`-in-a-transaction-with-`wal_level=minimal` can skip
WAL entirely). Both are things a backend hacker hits constantly when validating
a patch.

## Reading EXPLAIN (§ Using EXPLAIN)

- **Costs are in arbitrary units of sequential page fetches.** By convention
  `seq_page_cost = 1.0` and every other cost GUC is relative to it; the numbers
  are NOT milliseconds. [from-docs]
- **A node's cost is cumulative — it includes all child-node costs.** Read the
  tree bottom-up; the top node's total is the whole plan. [from-docs]
- **The two cost numbers are `startup_cost..total_cost`**: cost to return the
  *first* row vs the *last* row. A seq scan example: `pages*seq_page_cost +
  rows*cpu_tuple_cost` (e.g. 345 + 10000*0.01 = 445). [from-docs]
- **`rows` is rows EMITTED by the node, not rows scanned** — already reduced by
  that node's `WHERE` filter. So a filtered seq scan shows a low `rows` but its
  cost stays high (it still visits every tuple; cost may even rise from
  evaluating the filter). This is the single most-misread field. [from-docs]
- **`width` is the estimated average output row size in bytes.** [from-docs]
- **The planner deliberately ignores output-conversion and network-transmit
  cost** — it can't change them by picking a different plan. [from-docs]
- **`EXPLAIN ANALYZE` actually RUNS the query.** For DML, wrap in a transaction
  and `ROLLBACK`, or it mutates your tables. [from-docs]
- **`actual time=startup..total rows=N loops=M` — times are real milliseconds,
  per-iteration; multiply by `loops`** to get total time in that node. Because
  costs are arbitrary units and actuals are ms, the two columns won't line up.
  [from-docs]
- **Estimate-vs-actual divergence is the diagnostic signal**, but some
  divergence is benign-by-display: a `LIMIT` shows child costs *as if run to
  completion* even though execution stopped early; a merge join that rescans the
  inner side on duplicate outer keys counts each re-emission, inflating the
  inner child's actual `rows` above the relation's true size. [from-docs]
- **`Rows Removed by Filter`** appears only when ≥1 row was rejected — invaluable
  at join nodes to see selectivity misestimates. [from-docs]
- **Index-Only Scan prints `Heap Fetches: N`**; `0` means the visibility map let
  the index answer entirely without touching the heap. [from-docs]
- **`BUFFERS`** reports buffers hit/read/dirtied/written for the node + children;
  `ANALYZE` now implicitly enables `BUFFERS`. [from-docs]
- **`EXPLAIN ANALYZE` timing overhead can be significant** on systems with slow
  `gettimeofday()`; measure it with the `pg_test_timing` tool. [from-docs]

## Bulk loading (§ Populating a Database)

- **One big transaction beats per-row commit** — per-row commit pays
  transaction overhead on every row. [from-docs]
- **`COPY` is almost always faster than `INSERT`**, even prepared+batched
  `INSERT`, because it's one command for all rows. `PREPARE`/`EXECUTE` helps
  repeated `INSERT`s (skips re-parse/re-plan) but still loses to `COPY`.
  [from-docs]
- **`COPY` can skip WAL entirely** when run in the *same transaction* as the
  `CREATE TABLE` or `TRUNCATE` that made the table — but **only under
  `wal_level = minimal`**. Such commands guarantee crash safety with a single
  end-of-command `fsync` instead of full WAL. [from-docs]
  [verified-by-code, via knowledge/architecture/wal.md]
- **Create indexes AFTER the bulk load**, not before — building an index over
  existing data is cheaper than maintaining it per-inserted-row. [from-docs]
- **Drop foreign keys during large loads.** FK checks are not just slower
  per-row; the trigger event queue can overflow memory and cause swapping or
  outright failure. Re-add them after (bulk check is far cheaper). [from-docs]
- **Raise `maintenance_work_mem`** to speed `CREATE INDEX` and `ALTER TABLE ADD
  FOREIGN KEY` — it does little for `COPY` itself. [from-docs]
- **Raise `max_wal_size`** temporarily so bulk-load-driven checkpoints fire less
  often. [from-docs]
- **For loads into an archiving/replicated cluster, consider disabling archival
  + taking a fresh base backup afterward** rather than shipping a mountain of
  incremental WAL. [from-docs]
- **`ANALYZE` after the load is strongly recommended** (effectively mandatory) —
  fresh data with stale stats produces bad plans. [from-docs]
- **`pg_dump` already orders things correctly** (COPY, then indexes, then FKs)
  for a full dump; restore faster with `pg_restore --jobs=N` (parallel) and
  `psql -1`/`--single-transaction`. A **data-only** dump does NOT drop/recreate
  indexes, so those optimizations are back on you. [from-docs]

## Links into corpus

- [[knowledge/architecture/query-lifecycle.md]] — where planning/costing sits.
- [[knowledge/subsystems/optimizer.md]] — the cost model EXPLAIN surfaces.
- [[knowledge/subsystems/executor.md]] — the nodes whose actual time/loops show.
- [[knowledge/docs-distilled/planner-stats.md]] — the statistics half of this
  chapter (why estimates can be wrong).
- [[knowledge/architecture/wal.md]] — the WAL the `wal_level=minimal` COPY trick
  skips.
- [[knowledge/idioms/guc-variables.md]] — seq_page_cost / maintenance_work_mem /
  max_wal_size and friends.

## Confidence note

All claims `[from-docs]` from the two named subsections (fetched 2026-06-05).
The `wal_level=minimal` COPY-skips-WAL claim is additionally
`[verified-by-code]` via the WAL architecture doc. The parent
`performance-tips.html` page itself is only a ToC; this doc intentionally
distills its subsections.
