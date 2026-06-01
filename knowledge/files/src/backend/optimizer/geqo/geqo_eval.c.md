# geqo_eval.c — fitness function + tour-to-join-tree builder

- **Source:** 357 lines · **Last verified commit:** `ef6a95c7c64`

## Purpose

Evaluate a candidate gene tour (permutation of base relations) by building the
corresponding join tree and returning its `total_cost`. The tour-to-tree
builder, `gimme_tree`, is the load-bearing piece. [verified-by-code]

## Entry points

- `Cost geqo_eval(PlannerInfo *root, Gene *tour, int num_gene)` (line ~60) —
  switches into a private memory context, calls `gimme_tree`, computes
  fitness = `best_path->total_cost` or `DBL_MAX` on failure, then resets the
  context to free everything allocated during evaluation. [verified-by-code:102-132]
- `RelOptInfo *gimme_tree(PlannerInfo *root, Gene *tour, int num_gene)`
  (line ~163) — builds a left-deep-ish tree using "clumps" of already-joined
  relations. [verified-by-code]

## Mental model

A *Clump* is a sub-join already built (`{joinrel, size}`). `gimme_tree` walks
the tour, repeatedly attempting `make_join_rel` between the current clump and
the next gene; when no legal join exists it stashes the clump and starts a
new one, then re-merges. This handles join-order constraints (LATERAL,
outer joins) that pure permutation cannot. [from-comment:341, verified-by-code]

## Memory discipline

Each `geqo_eval` call resets a temp context (`mycontext`), so a million bad
chromosomes don't leak the planner's heap. [verified-by-code]
