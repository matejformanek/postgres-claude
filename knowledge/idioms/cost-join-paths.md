# Cost join paths — initial_cost / final_cost for nestloop, mergejoin, hashjoin

Join cost in PostgreSQL is **two-phase**: `initial_cost_*` runs
during path generation to get a quick upper-bound cost (cheap to
compute, accurate enough to prune most non-viable join orders);
`final_cost_*` runs only for paths that survive the initial
filter, doing the expensive selectivity + qual-cost work. The
two-phase split exists because cost_qual_eval is expensive and we
generate O(N²) candidate join paths but ultimately keep only a
handful. The `JoinCostWorkspace` carries state between phases.

Anchors:
- `source/src/backend/optimizer/path/costsize.c:3373` —
  initial_cost_nestloop [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:3455` —
  final_cost_nestloop [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:3658` —
  initial_cost_mergejoin [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:4297` —
  initial_cost_hashjoin [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:4416` —
  final_cost_hashjoin [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:3413-3434` —
  SEMI/ANTI/unique short-circuit [verified-by-code]
- `knowledge/idioms/cost-units-gucs.md` — companion
- `knowledge/idioms/cost-scan-paths.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The two-phase model

```
For each candidate (outer, inner, jointype):
    workspace = initial_cost_X(outer, inner, jointype, ...)
    if workspace.total_cost looks reasonable:
        path = create_join_path(...)
        final_cost_X(path, workspace, ...)   /* refine */
        add_path(rel, path)                  /* keeps best */
    else:
        discard
```

`add_path` may evict the candidate later if a better one is
found. The initial cost is allowed to be optimistic — if final
makes it worse, add_path drops it.

## initial_cost_nestloop

[verified-by-code `costsize.c:3373-3444`]

```c
void
initial_cost_nestloop(PlannerInfo *root, JoinCostWorkspace *workspace,
                      JoinType jointype, uint64 enable_mask,
                      Path *outer_path, Path *inner_path,
                      JoinPathExtraData *extra)
{
    disabled_nodes = (extra->pgs_mask & enable_mask) == enable_mask ? 0 : 1;
    disabled_nodes += inner_path->disabled_nodes + outer_path->disabled_nodes;

    cost_rescan(root, inner_path,
                &inner_rescan_start_cost, &inner_rescan_total_cost);

    startup_cost += outer_path->startup_cost + inner_path->startup_cost;
    run_cost += outer_path->total_cost - outer_path->startup_cost;
    if (outer_path_rows > 1)
        run_cost += (outer_path_rows - 1) * inner_rescan_start_cost;

    inner_run_cost = inner_path->total_cost - inner_path->startup_cost;
    inner_rescan_run_cost = inner_rescan_total_cost - inner_rescan_start_cost;

    if (jointype == JOIN_SEMI || jointype == JOIN_ANTI ||
        extra->inner_unique)
    {
        /* Stop after first match - postpone full cost to final */
        workspace->inner_run_cost = inner_run_cost;
        workspace->inner_rescan_run_cost = inner_rescan_run_cost;
    }
    else
    {
        /* Scan whole inner for each outer row */
        run_cost += inner_run_cost;
        if (outer_path_rows > 1)
            run_cost += (outer_path_rows - 1) * inner_rescan_run_cost;
    }

    workspace->disabled_nodes = disabled_nodes;
    workspace->startup_cost = startup_cost;
    workspace->total_cost = startup_cost + run_cost;
    workspace->run_cost = run_cost;
}
```

Two patterns to note:
- **Rescan cost is amortized** — for outer rows 2..N, only the
  rescan-cost (cheaper, since the inner is "warm") applies.
- **SEMI / ANTI / inner_unique defer accurate work to final** —
  they need to look at join quals to estimate "average outer rows
  before the first match", which is expensive.

## final_cost_nestloop

[verified-by-code `costsize.c:3455+`]

Refines via:
1. Real row count from the join rel.
2. Qual-eval cost via `cost_qual_eval`.
3. Per-tuple CPU multiplied by ntuples.
4. Parallel divisor on rows.

For SEMI/ANTI: estimates the "average position of first match" in
the inner scan, multiplied across outer rows. Uses
`approx_tuple_count` to project the join selectivity onto inner
positions.

## cost_rescan — the inner-side amortization

For a nestloop, the same inner relation is scanned for every
outer row. cost_rescan computes a CHEAPER "second time around"
cost:
- **Tuplestore / Materialize** below the inner — first scan costs
  full, subsequent scans cost only the tuplestore read.
- **Memoize** (PG 14+) — cache by inner-path's join keys; second
  occurrence of a key is free.
- **Sort** — first scan does the sort; subsequent scans read the
  sorted output.

Without rescan amortization, nestloop with a sub-Sort would be
massively overestimated.

## initial_cost_mergejoin

[verified-by-code `costsize.c:3658+`]

Mergejoin requires both inputs to be SORTED on the join key. Cost
components:
- **Sort costs** below (already in outer/inner_path.total_cost).
- **One full pass of both inputs** — cost is the sum of
  total_costs (no rescan; mergejoin advances both sides).
- **Skip-ahead optimization** — for some merge configurations,
  outer rows can be skipped when known not to match.

Mergejoin's per-tuple CPU is lower than hashjoin's (no hash
function call), so it can win when the inputs are already sorted.

## initial_cost_hashjoin

[verified-by-code `costsize.c:4297+`]

Cost components:
- **Build phase**: inner_path's total_cost + per-tuple hash
  insertion (cpu_operator_cost × num_hash_clauses × inner_rows).
- **Probe phase**: outer_path's total_cost + per-tuple hash
  lookup + match-fanout estimation.
- **Spill to disk if work_mem exceeded** — adds page-fetch costs
  for the batch tuplestores.

Hashjoin's per-output-row cost is low IF the hash table fits in
work_mem; otherwise it pays disk I/O for batched probes.

## final_cost_hashjoin

[verified-by-code `costsize.c:4416+`]

Refines via:
- Real `outer_matched_rows` count.
- Bucket-skew penalty (skewed inner-key distribution makes some
  buckets expensive).
- Multi-batch additional I/O.

## JoinCostWorkspace — the carry-over

```c
typedef struct JoinCostWorkspace
{
    Cost      startup_cost;
    Cost      total_cost;
    int       disabled_nodes;
    Cost      run_cost;             /* total - startup */
    /* hash-specific */
    Cost      inner_run_cost;        /* for SEMI/ANTI */
    Cost      inner_rescan_run_cost;
    int       numbatches;
    double    inner_rows_total;
    /* etc. */
} JoinCostWorkspace;
```

Lives on the stack during one initial → final cycle. Lets final
skip work that initial already did (sort cost, hash table size).

## SEMI / ANTI / inner_unique — the short-circuit

[verified-by-code `costsize.c:3413-3434`]

```c
if (jointype == JOIN_SEMI || jointype == JOIN_ANTI ||
    extra->inner_unique)
{
    /* defer to final_cost_nestloop */
}
else
{
    /* full inner scan per outer row */
    run_cost += inner_run_cost;
    if (outer_path_rows > 1)
        run_cost += (outer_path_rows - 1) * inner_rescan_run_cost;
}
```

Semi-/anti-join executors stop after the first match (or
non-match) per outer row, so the inner scan only goes as far as
needed. Average position of first match comes from the join
selectivity, which needs qual evaluation — too expensive for
initial.

`inner_unique` (PG 10+) is set when the planner proves the inner
relation has at most one matching row per outer (e.g., FK +
unique index). Same short-circuit semantics.

## Parallel-aware join costing

For parallel joins (`path->parallel_workers > 0`):
- **CPU work divides** by parallel_divisor.
- **Row count divides** by parallel_divisor (each worker sees a
  share).
- **Hash table build** in parallel hash join: divided across
  workers (after PHJ_BUILD_HASH_INNER barrier).

The decision to consider parallel is gated by
`max_parallel_workers_per_gather` and the path's parallel-safety.

## Cost-of-rescan distinction

A nestloop's outer = sub-plan X (cost S). If X is rescanned
many times:
- Without amortization: cost ≈ outer_rows × X.total_cost
  (overestimate; the planner would never pick this).
- With cost_rescan: cost ≈ X.total_cost + (outer_rows - 1) ×
  X.rescan_cost.

This is why nestloop can win against hashjoin when there's a
cheap-rescan inner (small, indexed by parameterization).

## Common review-time concerns

- **initial is allowed to be optimistic** — final corrects.
- **cost_rescan is non-trivial** — buggy rescan-cost
  underestimation makes nestloops too attractive.
- **SEMI/ANTI defer to final** — initial may miss bad cases.
- **inner_unique = true is a strong cost reduction** —
  ensure the planner sets it (FK + unique index).
- **Parallel cost divisor includes a fractional leader term** —
  `workers + max(0, 1.0 - 0.3 × workers)`; see
  `cost-parallel-adjustments`.
- **Hashjoin disk-spill batches add I/O cost** — high-cardinality
  inner pays for multi-batch probes.

## Invariants

- **[INV-1]** initial_cost_* produces an upper-bound cost from
  cheap inputs only.
- **[INV-2]** final_cost_* refines using qual evaluation +
  real row estimates.
- **[INV-3]** disabled_nodes accumulates from inputs + self-disable.
- **[INV-4]** SEMI/ANTI/inner_unique short-circuit inner scan
  cost.
- **[INV-5]** Parallel join cost divides CPU + rows by
  parallel_divisor (`workers + max(0, 1.0 - 0.3 × workers)`).

## Useful greps

- The cost-join family:
  `grep -n '^initial_cost_nestloop\|^final_cost_nestloop\|^initial_cost_mergejoin\|^initial_cost_hashjoin\|^final_cost_hashjoin' source/src/backend/optimizer/path/costsize.c | head -10`
- JoinCostWorkspace:
  `grep -RIn 'JoinCostWorkspace' source/src/include/nodes source/src/backend/optimizer | head -10`
- cost_rescan + materialization:
  `grep -n '^cost_rescan\|inner_rescan' source/src/backend/optimizer/path/costsize.c | head -10`
- inner_unique flag:
  `grep -RIn 'inner_unique\|innerunique' source/src/backend/optimizer | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 3373 | initial_cost_nestloop |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 3413 | SEMI/ANTI/unique short-circuit |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 3455 | final_cost_nestloop |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 3658 | initial_cost_mergejoin |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 4297 | initial_cost_hashjoin |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 4416 | final_cost_hashjoin |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | — | full module |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-cost-model-knob`](../scenarios/add-new-cost-model-knob.md)
- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/cost-units-gucs.md` — base GUCs.
- `knowledge/idioms/cost-scan-paths.md` — sub-paths feeding
  joins.
- `knowledge/idioms/parallel-hash-join.md` — executor side.
- `knowledge/idioms/memoize-nestloop.md` — modern rescan
  amortization.
- `knowledge/idioms/foreign-key-selectivity.md` —
  get_foreign_key_join_selectivity.
- `knowledge/data-structures/plannerinfo.md` — Path + JoinPath
  structs.
- `knowledge/subsystems/optimizer.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `source/src/backend/optimizer/path/costsize.c` — full module.
