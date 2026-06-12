---
source_url: https://www.postgresql.org/docs/current/executor.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §52.5: The Executor

The high-level mental model the docs give for `src/backend/executor/`: a
demand-pull (Volcano) iterator tree, with `ModifyTable` turning every write into a
`SELECT` underneath. The orientation a new executor hacker reads before `nodeXxx.c`.

## Demand-pull / Volcano iterator [from-docs]

- The executor takes the planner's plan tree and **recursively processes it to
  extract rows** — *"essentially a demand-pull pipeline mechanism."* [from-docs]
- Each time a plan node is called it must **deliver one more row, or report it is
  done** (returns NULL when exhausted). Parents pull from children on demand; no
  child runs ahead of demand except where a node must materialize. [from-docs]
  [verified-by-code, source/src/backend/executor/execProcnode.c — `ExecProcNode`
  dispatch; via knowledge/subsystems/executor.md]
- Each node also **applies the selection (filter) and projection** the planner
  assigned to it — qual evaluation and target-list projection are per-node, not
  centralized. [from-docs]

## The worked example: MergeJoin → Sort → SeqScan [from-docs]

The docs trace a top `MergeJoin`:
1. MergeJoin demands a row from a subplan (e.g. its `lefttree`).
2. A `Sort` node receiving the demand recursively pulls **all** rows from its
   child (a blocking node), sorts, then returns them one at a time.
3. The `SeqScan` at the bottom fetches actual heap rows.
4. When a subplan is exhausted (child returns NULL) the join eventually returns
   NULL upward. [from-docs]

This is the canonical illustration of **blocking vs streaming** nodes: Sort must
drain its input before yielding its first row; SeqScan/MergeJoin stream.
[inferred, from-docs]

## Writes are SELECTs under `ModifyTable` [from-docs]

- For a `SELECT`, the top-level executor just **ships each plan-tree row to the
  client**. [from-docs]
- `INSERT ... SELECT`, `UPDATE`, `DELETE`, and `MERGE` are **effectively SELECTs
  under a top `ModifyTable` node**: [from-docs]
  - **UPDATE** plan returns the new column values **plus the TID** of the original
    target row; `ModifyTable` writes the new version and marks the old deleted.
  - **DELETE** plan returns **only the TID**; `ModifyTable` visits each and marks
    it deleted.
  - **MERGE** plan joins source+target, returns columns needed by any `WHEN`
    clause **plus the target TID**; `ModifyTable` picks the matching `WHEN` and
    does the insert/update/delete.
  - **`INSERT ... VALUES`** builds a trivial plan: a single `Result` node
    computing one row, fed up to `ModifyTable`. [from-docs]
  [verified-by-code, source/src/backend/executor/nodeModifyTable.c; via
  knowledge/subsystems/executor.md]

The TID-threading is the key takeaway: the plan tree below `ModifyTable` does the
*finding*; `ModifyTable` does the *mutating*, addressed by TID.

## Links into corpus

- [[knowledge/subsystems/executor.md]] — the per-node lifecycle
  (`ExecInitNode`/`ExecProcNode`/`ExecEndNode`) the docs gloss over.
- [[knowledge/architecture/executor.md]] — architecture-level companion.
- [[knowledge/architecture/query-lifecycle.md]] — where the executor sits after
  parse/rewrite/plan.
- [[knowledge/docs-distilled/query-path.md]] — the upstream stages.
- [[knowledge/docs-distilled/planner-optimizer.md]] — what produces the plan tree
  this stage consumes.

## Gaps / follow-ups

- The docs omit **portals** and `ExecutorRun`/`ExecutorFinish` phasing entirely;
  those live in the executor subsystem doc + `pquery.c`. SELECT INTO and utility
  statements (non-plan paths) are also out of scope for this chapter.
