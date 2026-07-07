# View pushdown via rewriter — ON SELECT rules → subquery RTE

A SQL view is implemented in PostgreSQL as an **ON SELECT rule
on a relation with relkind = 'v'**. When a query references the
view, the rewriter's `ApplyRetrieveRule` replaces the view's
RangeTblEntry (kind RTE_RELATION) with an RTE_SUBQUERY whose
subselect is the view's definition. From the planner's POV
there's no view — only a subquery. This is the substrate for
WITH CHECK OPTION, updatable-view expansion, security-barrier
views, and the inlining heuristics that decide whether to flatten
the subquery into the outer query.

Anchors:
- `source/src/backend/rewrite/rewriteHandler.c:1759` —
  ApplyRetrieveRule [verified-by-code]
- `source/src/backend/rewrite/rewriteHandler.c:1885` —
  recursive fireRIRrules on rule action [verified-by-code]
- `source/src/backend/rewrite/rewriteHandler.c:1899` —
  rtekind = RTE_SUBQUERY swap [verified-by-code]
- `source/src/backend/rewrite/rewriteHandler.c:1901` —
  security_barrier flag set [verified-by-code]
- `knowledge/idioms/row-security-policy-application.md` —
  companion (RLS uses similar quals-injection)
- `knowledge/idioms/security-barrier-views.md` — companion
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The rewriter flow

[from-code `rewriteHandler.c`]

```
QueryRewrite(parsetree):
  for each query in inputs:
    fireRIRrules(query)        # ApplyRetrieveRule per view RTE
    fireRules(query)            # other rules (INSERT/UPDATE/DELETE)
```

`fireRIRrules` ("RIR" = "Retrieve, Instead, Rules" historical
name) walks the range table and for any RTE pointing at a
view, expands it via `ApplyRetrieveRule`.

## ApplyRetrieveRule — the swap

[verified-by-code `rewriteHandler.c:1759-1900`]

Simplified:

```c
static Query *
ApplyRetrieveRule(Query *parsetree, RewriteRule *rule, int rt_index,
                  Relation relation, List *activeRIRs)
{
    Query *rule_action = copyObject(linitial(rule->actions));

    /* Recursively expand views WITHIN the rule action */
    rule_action = fireRIRrules(rule_action, activeRIRs);

    /* Replace the RTE_RELATION with RTE_SUBQUERY */
    rte->rtekind = RTE_SUBQUERY;
    rte->subquery = rule_action;
    rte->security_barrier = RelationIsSecurityView(relation);

    /* Drop now-unused fields */
    rte->relid = InvalidOid;
    rte->relkind = 0;
    rte->tablesample = NULL;
    /* ... */
}
```

Three steps:
1. Copy the rule action (the view's SELECT).
2. Recursively expand views referenced inside the action.
3. Mutate the original RTE in place: now it's a subquery RTE.

After this, the outer query no longer mentions the view; it
mentions a subquery whose plan is the view's definition.

## The activeRIRs cycle guard

```c
List *activeRIRs;
```

To prevent infinite recursion on self-referential views (or
mutually recursive ones), `fireRIRrules` tracks the active set
of views being expanded. If a view tries to expand itself, it's
detected and reported as a recursion error.

## security_barrier — the planner gate

[verified-by-code `rewriteHandler.c:1901`]

```c
rte->security_barrier = RelationIsSecurityView(relation);
```

The `security_barrier` flag tells the planner: **don't push
qual conditions through this subquery boundary**, even if the
qual is otherwise pushdown-eligible. This protects against
side-channel leaks where a leaky qual (like a malicious
operator) sees rows the view was supposed to hide.

[per `security-barrier-views` companion]

## Subquery flattening (or not)

After the view becomes a subquery RTE, the planner's
`pull_up_subqueries` may or may not inline it back into the
outer query:

- **Simple views** (no aggregation, no DISTINCT, no LIMIT) →
  often pulled up; their predicates merge with the outer
  query's.
- **Aggregate / DISTINCT / LIMIT views** → kept as subquery;
  evaluated separately.
- **`security_barrier = true`** → never pulled up; the
  barrier is enforced.

This is what makes simple views as fast as joining against the
underlying table directly: pullup eliminates the subquery
boundary in the plan.

## Updatable views — INSTEAD OF triggers

If the view is **simple updatable** (no aggregation, single
base table, etc.), the rewriter can route INSERT / UPDATE /
DELETE through to the base table directly. Otherwise the user
needs an `INSTEAD OF` trigger.

Updatability is computed at view-definition time and stored in
`pg_rewrite`. The rewriter checks it before allowing DML on
the view.

## WITH CHECK OPTION

```sql
CREATE VIEW v AS SELECT * FROM t WHERE col > 0 WITH CASCADED CHECK OPTION;
```

For updatable views, `WITH CHECK OPTION` enforces that
INSERT / UPDATE through the view satisfies the view's WHERE
clause. The rewriter emits a post-write check that fails if the
new row wouldn't be visible through the view.

CASCADED extends the check through any nested views.

## Recursive views (WITH RECURSIVE)

A `WITH RECURSIVE view_def AS (...)` view doesn't go through
ApplyRetrieveRule's standard path — recursive CTEs have their
own expansion in the analyzer. The rewriter's main job is just
to inject the view's RTE.

## The pg_rewrite catalog

[from-code]

A view's ON SELECT rule lives as a row in `pg_rewrite` with:
- `ev_class` → the view's relation.
- `ev_type` → `'1'` for SELECT.
- `is_instead` → `true` (the rule REPLACES the relation scan).
- `ev_action` → the parsed Query tree (encoded as a string).

Multiple rules per relation are possible (INSERT/UPDATE/DELETE
DO INSTEAD rules), but only one ON SELECT rule.

## Common review-time concerns

- **Recursive view expansion** — activeRIRs guards against
  infinite recursion.
- **security_barrier blocks pushdown** — sometimes a perf
  regression; sometimes a security requirement.
- **Pullup decisions matter** — EXPLAIN may show the view
  inlined or as a subquery node.
- **WITH CHECK OPTION is post-write** — failed checks roll
  back the row.
- **Updatable view rules in pg_rewrite** — distinct from
  INSTEAD OF triggers; check both.
- **Single ON SELECT rule per view** — enforced at view
  creation.

## Invariants

- **[INV-1]** View RTE → subquery RTE via ApplyRetrieveRule.
- **[INV-2]** activeRIRs detects recursion.
- **[INV-3]** security_barrier flag prevents qual pushdown.
- **[INV-4]** Simple updatable views route DML to base table.
- **[INV-5]** WITH CHECK OPTION is post-write enforced.

## Useful greps

- The entry point:
  `grep -n 'ApplyRetrieveRule\|fireRIRrules' source/src/backend/rewrite/rewriteHandler.c | head -10`
- security_barrier wiring:
  `grep -RIn 'security_barrier' source/src/backend/rewrite source/src/backend/optimizer | head -10`
- Subquery pullup:
  `grep -RIn 'pull_up_subqueries\|pull_up_simple_subquery' source/src/backend/optimizer/prep | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/rewrite/rewriteHandler.c`](../files/src/backend/rewrite/rewriteHandler.c.md) | 1759 | ApplyRetrieveRule |
| [`src/backend/rewrite/rewriteHandler.c`](../files/src/backend/rewrite/rewriteHandler.c.md) | 1885 | recursive fireRIRrules on rule action |
| [`src/backend/rewrite/rewriteHandler.c`](../files/src/backend/rewrite/rewriteHandler.c.md) | 1899 | rtekind = RTE_SUBQUERY swap |
| [`src/backend/rewrite/rewriteHandler.c`](../files/src/backend/rewrite/rewriteHandler.c.md) | 1901 | security_barrier flag set |
| [`src/include/catalog/pg_rewrite.h`](../files/src/include/catalog/pg_rewrite.h.md) | — | catalog row |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/row-security-policy-application.md` —
  RLS uses similar quals-injection in rewriter.
- `knowledge/idioms/security-barrier-views.md` — the
  security_barrier flag's planner semantics.
- `knowledge/idioms/cached-plan-invalidation.md` —
  ALTER VIEW invalidates plans.
- `knowledge/data-structures/plannerinfo.md` —
  planner_root.glob->hasRowSecurity reflects view-side flags.
- `knowledge/subsystems/parser-and-rewrite.md` — rewriter.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `.claude/skills/parser-and-nodes/SKILL.md` — node
  manipulation conventions.
- `source/src/backend/rewrite/rewriteHandler.c:1759` —
  ApplyRetrieveRule.
- `source/src/include/catalog/pg_rewrite.h` — catalog row.
