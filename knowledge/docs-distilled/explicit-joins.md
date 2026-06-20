---
source_url: https://www.postgresql.org/docs/current/explicit-joins.html
fetched_at: 2026-06-20T19:55:00Z
anchor_sha: dc5116780846
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Controlling the Planner with Explicit JOIN Clauses (§16.5)

The "how to bound the join-order search" leaf of the Performance Tips chapter.
Key mental model: by default the planner is **free to reorder joins** for both
comma-separated `FROM` lists and explicit `INNER`/`CROSS` joins — they're
semantically identical. The two collapse-limit GUCs let you trade planning time
for plan freedom, up to forcing a literal join order.

## Reordering freedom and its cost

- For a simple `FROM a, b, c WHERE ...`, the planner may pick **any** join order
  (A⋈B⋈C, B⋈C⋈A, …) — all produce identical results but wildly different costs.
  [from-docs]
- These three are **logically equivalent** and, by default, planned identically:
  `FROM a, b, c WHERE a.id=b.id AND b.ref=c.id`; the same with `CROSS JOIN`;
  and `FROM a JOIN (b JOIN c ON b.ref=c.id) ON a.id=b.id`. "Explicit inner join
  syntax … is semantically the same as listing the input relations in `FROM`, so
  it does not constrain the join order." [from-docs]
- The number of possible join orders grows **exponentially** with table count;
  beyond ~10 input relations exhaustive search is impractical and the planner
  switches to the **genetic** (GEQO) probabilistic search, gated by the
  `geqo_threshold` GUC. [from-docs]

## OUTER joins do constrain order

- `LEFT`/`RIGHT JOIN` reduce the planner's freedom but usually leave *some*
  rearrangement room. In `a LEFT JOIN (b JOIN c ON b.ref=c.id) ON a.id=b.id`,
  B⋈C must happen before A is joined in, so that unmatched A-rows can still be
  emitted with nulls. [from-docs]
- `FULL JOIN` **completely** constrains the join order — no reordering. [from-docs]

## The two collapse-limit GUCs

- **`join_collapse_limit`** — controls when the planner "flattens" explicit JOIN
  constructs into the surrounding `FROM` item list (making them reorderable).
  Setting it to **1** prevents flattening, so the planner **honors the explicit
  JOIN nesting as written** — i.e. you hand-pick the join order. [from-docs]
- **`from_collapse_limit`** — the sibling knob for **subqueries**: controls when
  a subquery is flattened (collapsed) into the parent query's `FROM` list.
  Collapsing usually yields better plans (enables cross-boundary qual
  optimization) but raises planning complexity; the planner won't collapse if the
  result would exceed `from_collapse_limit` `FROM` items. [from-docs]
- The two are "similarly named because they do almost the same thing: one
  controls when the planner will 'flatten out' subqueries, and the other controls
  when it will flatten out explicit joins." [from-docs]
- **Partial control:** `join_collapse_limit = 1` can pin *part* of the order —
  `FROM a CROSS JOIN b, c, d, e` forces A⋈B first but leaves c/d/e free,
  cutting the search space by a factor. [from-docs]

## Recommended settings

- Either set `join_collapse_limit = from_collapse_limit` (explicit joins and
  subqueries behave the same), OR set `join_collapse_limit = 1` to take manual
  control of join order via explicit JOIN syntax. [from-docs]
- This leaf gives usage guidance, **not** default values — the defaults (both 8
  in stock PG) live in the runtime-config-query GUC reference, not here. [inferred]

## Links into corpus

- `knowledge/subsystems/optimizer.md` — `join_search_one_level` /
  `make_rel_from_joinlist`, where collapse limits gate the deconstruct of the
  jointree.
- `knowledge/docs-distilled/planner-optimizer.md` — the planner-pipeline
  overview this knob sits inside.
- `knowledge/docs-distilled/geqo.md`, `knowledge/docs-distilled/geqo-intro.md` —
  the genetic search `geqo_threshold` hands off to when the table count is large.
- `knowledge/idioms/cost-join-paths.md` — how candidate join orders are costed.
- `knowledge/idioms/guc-variables.md` — the GUC machinery behind both limits.
- `knowledge/data-structures/plannerinfo.md`,
  `knowledge/data-structures/reloptinfo.md` — the join-search state.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/explicit-joins.html (PG18). Default
  values (8/8) are deliberately NOT in this page; cross-check
  runtime-config-query before asserting them.
