# Cost parallel adjustments — get_parallel_divisor + parallel-aware costing

When a path is partial (parallel-aware), its CPU cost and row
count are scaled down by a **parallel divisor** that represents
"how many effective workers are doing the work, counting the
leader's fractional contribution". The leader contributes
fractionally because it's also draining TupleQueues; the
heuristic is `1.0 - 0.3 × parallel_workers`, clamped to non-
negative. So with 1 worker the divisor is 1.7 (leader does most
of the work); with 4+ workers the leader's contribution clamps
to zero and the divisor equals worker count. The disk I/O cost
is deliberately NOT divided — the comment explains OS prefetch
already amortizes I/O.

Anchors:
- `source/src/backend/optimizer/path/costsize.c:6618` —
  get_parallel_divisor [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:6633-6640` —
  leader_contribution formula [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:311-331` —
  cost_seqscan parallel adjustment [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:319-324` —
  "disk cost can't be amortized" comment [verified-by-code]
- `source/src/backend/optimizer/path/costsize.c:144` —
  max_parallel_workers_per_gather = 2 default [verified-by-code]
- `knowledge/idioms/cost-units-gucs.md` — companion
- `knowledge/idioms/cost-scan-paths.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The divisor formula

[verified-by-code `costsize.c:6618-6643`]

```c
static double
get_parallel_divisor(Path *path)
{
    double parallel_divisor = path->parallel_workers;

    /*
     * ... when there is only one worker, the leader often makes a
     * very substantial contribution ... by the time we reach 4
     * workers, the leader no longer makes a meaningful contribution.
     * Thus, for now, estimate that the leader spends 30% of its time
     * servicing each worker ...
     */
    if (parallel_leader_participation)
    {
        double leader_contribution;
        leader_contribution = 1.0 - (0.3 * path->parallel_workers);
        if (leader_contribution > 0)
            parallel_divisor += leader_contribution;
    }
    return parallel_divisor;
}
```

| `parallel_workers` | `leader_contribution` | `parallel_divisor` |
|---|---|---|
| 1 | 0.7 | 1.7 |
| 2 | 0.4 | 2.4 |
| 3 | 0.1 | 3.1 |
| 4 | -0.2 → 0 (clamped) | 4.0 |
| 5 | -0.5 → 0 (clamped) | 5.0 |
| N ≥ 4 | 0 | N |

The 30%-per-worker is the "leader is busy servicing each worker"
estimate. The clamp means past 3 workers the leader is purely a
funnel.

## Where the divisor applies

[verified-by-code `costsize.c:311-330` (cost_seqscan) + similar in others]

```c
if (path->parallel_workers > 0)
{
    double parallel_divisor = get_parallel_divisor(path);
    cpu_run_cost /= parallel_divisor;
    /* disk_run_cost NOT divided */
    path->rows = clamp_row_est(path->rows / parallel_divisor);
}
```

Three quantities scale:
- **CPU run cost** — N workers share CPU work.
- **Row count** — each worker handles 1/divisor of the rows
  (relevant for upstream nodes).
- **(NOT disk I/O cost)** — see "I/O exception" below.

## The I/O exception

[verified-by-code `costsize.c:319-324`]

> It may be possible to amortize some of the I/O cost, but
> probably not very much, because most operating systems already
> do aggressive prefetching. For now, we assume that the disk
> run cost can't be amortized at all.

Why this matters:
- Page reads are dominated by OS prefetch.
- Parallel workers reading the same heap pages don't
  meaningfully reduce wall-clock I/O.
- Disk cost stays the same regardless of worker count.

This is a CONSERVATIVE assumption. Storage tiers with high
random-access cost (e.g., S3-backed) would benefit from
amortization, but PG doesn't model it.

## parallel_setup_cost and parallel_tuple_cost

[via cost.h constants]

These don't go through the divisor; they apply at the Gather
node:

| GUC | Default | Where |
|---|---|---|
| `parallel_setup_cost` | 1000.0 | One-time at Gather init |
| `parallel_tuple_cost` | 0.1 | Per tuple passing worker→leader |

So a parallel plan's TOTAL cost includes:
- Sub-path costs (CPU/divisor + disk_unchanged) for each parallel-aware operator below.
- Plus `parallel_setup_cost` at Gather (one-shot).
- Plus `output_rows × parallel_tuple_cost` (queue overhead).

For small queries this fixed setup cost discourages parallelism
— a plan returning 10 rows isn't worth 1000 cost-units of worker
startup.

## Why the divisor is fractional

A pure integer divisor (just `parallel_workers`) would
**under-cost** 1-worker plans: the leader actually does
significant work, but pure integer math says 1 worker = 100% of
work. The fractional model corrects this:
- 1 worker means "1 worker + leader doing ~70%" = 1.7 effective
  workers.
- Workers exceed 3 → leader contribution drops to 0.

This formula was added when `parallel_leader_participation` was
introduced; before that, costing assumed integer division.

## Interaction with parallel_leader_participation GUC

```sql
SET parallel_leader_participation = off;
```

The leader stops pulling tuples from the child; it only drains
worker queues. The divisor becomes just `parallel_workers` (no
fractional add). This is appropriate when:
- The leader has heavy post-Gather work (e.g., final aggregation).
- Profiling shows leader CPU is the bottleneck.

By default ON; uncommon to set OFF.

## Cap by max_parallel_workers_per_gather

[verified-by-code `costsize.c:144`]

```c
int max_parallel_workers_per_gather = 2;
```

The planner never proposes more workers than this. With
`max_parallel_workers_per_gather = 2`, all parallel paths have
`parallel_workers ≤ 2`. Raising it lets the planner consider
plans with more workers; production tuning at ≤ (cores - 2)
typically.

There's also a global cap `max_parallel_workers` (default 8) for
the cluster-wide pool, and `max_worker_processes` (default 8)
for total bgworkers including parallel.

## Parallel-aware paths only

The divisor applies ONLY to paths where the *child* is
parallel-aware. A serial scan below a Gather has parallel_workers
= 0 and doesn't divide. The planner generates partial paths
separately from full paths; partial paths use the divisor.

## Append + parallel-aware children

For a `Parallel Append` over partition tree:
- Each child (partition scan) is parallel-aware.
- The Append distributes children across workers (not within
  child).
- Each child's parallel_workers is set per partition cost.

`append_nonpartial_cost` handles the case where some children
are non-parallel (subpaths added separately).

## EXPLAIN-visible parallel costs

```
Gather  (cost=1000.00..123456.00 rows=N width=...)
  Workers Planned: 2
  ->  Parallel Seq Scan on big_table  (cost=0.00..98765.43 rows=M width=...)
```

The Gather's startup includes `parallel_setup_cost = 1000`. The
Parallel Seq Scan's cost is the divided cost. `Workers
Planned: 2` reflects what the planner chose; `Workers Launched
N` at ANALYZE shows actual runtime count (may be lower under
pool pressure).

## Common review-time concerns

- **Divisor depends on `parallel_leader_participation`** — toggling
  changes cost estimates and may flip the chosen plan.
- **0.3 × N is a heuristic, not derived** — comment says "early
  experience". Don't tune it without data.
- **Disk cost NOT divided** — I/O parallelism is OS prefetch's
  domain.
- **parallel_setup_cost suppresses parallelism for small
  queries** — tune down for cheap-startup workloads.
- **Workers > 3 are fully effective** — leader contribution
  is 0 at 4+ workers.
- **Cap by max_parallel_workers_per_gather** before considering
  the per-path cost — the planner clamps before costing.

## Invariants

- **[INV-1]** `parallel_divisor = parallel_workers + max(0, 1.0
  - 0.3 × parallel_workers)` (when leader_participation = on).
- **[INV-2]** Divisor applies to CPU + rows, NOT disk_run_cost.
- **[INV-3]** Gather adds `parallel_setup_cost` once +
  `output_rows × parallel_tuple_cost`.
- **[INV-4]** `max_parallel_workers_per_gather` caps per-path
  worker count; `max_parallel_workers` caps cluster-wide.
- **[INV-5]** With `parallel_leader_participation = off`,
  divisor reduces to plain worker count.

## Useful greps

- The divisor:
  `grep -n '^get_parallel_divisor\|leader_contribution' source/src/backend/optimizer/path/costsize.c | head -10`
- Callers:
  `grep -RIn 'get_parallel_divisor' source/src/backend/optimizer | head -10`
- Setup cost / tuple cost:
  `grep -n 'parallel_setup_cost\|parallel_tuple_cost' source/src/backend/optimizer/path/costsize.c | head -10`
- Worker count caps:
  `grep -n 'max_parallel_workers_per_gather\|max_parallel_workers' source/src/backend/utils/misc/guc_tables.c | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 144 | max_parallel_workers_per_gather = 2 default |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 311 | cost_seqscan parallel adjustment |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 319 | "disk cost can't be amortized" comment |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 6618 | get_parallel_divisor |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | 6633 | leader_contribution formula |
| [`src/backend/optimizer/path/costsize.c`](../files/src/backend/optimizer/path/costsize.c.md) | — | full module |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/cost-units-gucs.md` — base cost GUCs.
- `knowledge/idioms/cost-scan-paths.md` — where the divisor
  is applied at the bottom of scan plans.
- `knowledge/idioms/cost-join-paths.md` — parallel join cost.
- `knowledge/idioms/parallel-gather-merge.md` — executor side
  consuming parallel paths.
- `knowledge/idioms/parallel-hash-join.md` — sibling parallel
  node.
- `knowledge/data-structures/plannerinfo.md` — Path.parallel_workers,
  parallel_aware, parallel_safe.
- `knowledge/subsystems/parallel-query.md` — module overview.
- `.claude/skills/executor-and-planner/SKILL.md` — companion.
- `.claude/skills/parallel-query/SKILL.md` — planning side.
- `source/src/backend/optimizer/path/costsize.c` — full module.
