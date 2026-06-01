# rewriteHandler.c

- **Source:** `source/src/backend/rewrite/rewriteHandler.c` (4870 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (entry + ordering; per-feature bodies skim)

## Purpose

Primary module of the **query rewriter** — the second post-parser pass.
Takes a single analyzed `Query` and returns a `List<Query>` after applying:

1. Stored rules (`pg_rewrite` ON INSERT/UPDATE/DELETE/SELECT).
2. View expansion (a special case of an ON SELECT rule, called "RIR" —
   "Retrieve-Instead-Retrieve" in the historic PostQUEL terms used in
   comments).
3. Row-Level Security policy quals/with-checks.
4. SEARCH / CYCLE clause expansion for recursive CTEs (a convenient
   hookup point; nothing to do with rules).
5. GRAPH_TABLE lowering into a relational subquery.

[from-comment] `:3-19`

## The top entry: `QueryRewrite` `:4780-4870`

```
QueryRewrite(parsetree)
  ├─ Step 1: RewriteQuery(parsetree, ...)  → non-SELECT rules
  │     produces List<Query>
  ├─ Step 2: for each q in list: fireRIRrules(q, NIL)
  │     view expansion + RLS
  └─ Step 3: re-assign canSetTag among the resulting queries
     (original keeps it; else last INSTEAD of matching CmdType gets it)
```

Asserted preconditions: `parsetree->querySource == QSRC_ORIGINAL` and
`canSetTag == true`. `:4794-4795`

## Step 1 — `RewriteQuery` `:4044-…`

Walks DML targets and applies stored rules:

1. **Process WITH-clause data-modifying CTEs first** (recursively call
   `RewriteQuery`). Avoid re-rewriting already-processed CTEs in
   product queries via the `num_ctes_processed` counter. `:4067-4141`
2. **If the statement is INSERT/UPDATE/DELETE/MERGE**, adjust the
   targetlist (`rewriteTargetListIU` for INSERT/UPDATE — fills missing
   columns with defaults, processes generated columns, processes
   ON CONFLICT DO UPDATE set lists) and then fire matching rules via
   `fireRules` `:4358`. `:4151-…`
3. **SELECT statements are NOT rewritten here** — their RIR rules /
   view expansion happen in Step 2 instead. The comment is explicit at
   `:4147-4149`.

`fireRules` `:2484` walks the rules and partitions them into:

- *Unconditional INSTEAD* rules → replace the original query.
- *Conditional INSTEAD* rules → produce a product query plus a modified
  original whose qual is the negation (`qual_product`).
- *Non-INSTEAD ("DO ALSO")* rules → produce additional product queries
  alongside the original.

Each product query is then recursively passed back into `RewriteQuery`
(detection of infinite recursion uses the `rewrite_events` list keyed
on `(relation_oid, cmdtype)`). `:4519`

## Step 2 — `fireRIRrules` `:2042-2410`

Per-Query walker that does **four** ordered things:

1. **Expand SEARCH/CYCLE clauses in CTEs.** Convenient hook; not
   rule-related. `:2049-2063` calls `rewriteSearchAndCycle`.
2. **Per-RTE view expansion** by walking `rtable` and:
   - lowering `RTE_GRAPH_TABLE` to `RTE_SUBQUERY` via `rewriteGraphTable`
     `:2088-2091`, then;
   - recursing into `RTE_SUBQUERY` RTEs `:2098-2109`;
   - for `RTE_RELATION` RTEs that aren't materialized views or the
     `EXCLUDED` pseudo-rel of ON CONFLICT, collecting RIR (ON SELECT)
     rules and applying them via `ApplyRetrieveRule` `:2200-2204`;
   - recursion-loop check via `activeRIRs` list `:2189-2194`.
3. **Recurse into CTE bodies** `:2215-2227` and **SubLink subqueries**
   `:2230-2248` (also setting `hasRowSecurity` propagation).
4. **Apply RLS policies last** `:2249-…` because policy quals may carry
   sublinks of their own; doing them inside the loop above would make
   `query_tree_walker` recurse into the quals a second time. This
   ordering comment at `:2250-2255` is load-bearing.

## Step 3 — canSetTag adjustment `:4838-4867`

If the original query survives the rewrite, it keeps `canSetTag`.
Otherwise, the *last* INSTEAD query whose command type matches the
original's command type is promoted. May leave nobody with the tag — the
tcop layer fabricates a default tag in that case.

## AcquireRewriteLocks `:148-…`

Re-acquires the relation locks recorded in the RTEs of any non-fresh
Query (i.e. a Query that came from `pg_rewrite` storage or the plan
cache). Skipped for parser output because the parser already took those
locks. Also fixes up join-RTE alias-var references to dropped columns
(replaces them with null pointers) — necessary because stored rules can
outlive the columns they refer to. `:103-146`

## Other features inside this file

- `rewriteTargetListIU` `:77-83` — fills in defaults / generated columns
  / OVERRIDING semantics for INSERT/UPDATE target lists.
- `rewriteValuesRTE` `:89-91` — same, but reaches into the multi-row
  VALUES RTE.
- `rewriteValuesRTEToNulls` `:92` — when an INSERT with no input columns
  becomes a "DEFAULT VALUES" form, nuke the row expressions.
- `markQueryForLocking` `:93-95` — propagate FOR UPDATE/SHARE into
  subqueries.
- `matchLocks` `:96-97` — given an event + relation, return the
  applicable rules (matches `pg_rewrite.ev_type` against `event` and
  honors enabling state).
- `adjust_view_column_set` `:99` — used by RLS to remap column bitmaps
  through a view's targetlist.
- `get_generated_columns` `:100` — collect stored-or-virtual generated
  column expressions for an INSERT/UPDATE rewrite.

## Critical ordering claims (the section most likely to be wrong)

1. **DML rules fire before SELECT rules (view expansion).** `RewriteQuery`
   handles non-SELECT events; SELECT/view expansion is in Step 2 via
   `fireRIRrules`. Documented at `:4147-4149`.
2. **Within `fireRIRrules`, RLS is applied LAST**, after view expansion
   and after recursion into sublinks/CTEs. The reason is sublink
   double-recursion avoidance. `:2250-2255` is the comment establishing
   this.
3. **WITH-clause data-modifying CTEs are rewritten BEFORE the outer
   statement**, because rule actions on the outer statement may copy the
   WITH clauses into product queries. `:4055-4066`.
4. **Lock re-acquisition** (`AcquireRewriteLocks`) is the *first* step
   for any Query that didn't come straight from the parser. Otherwise
   schema changes mid-rewrite could break us. The function header
   explains this at `:128-133`.

## Caveats and known sharp edges

- `DefineQueryRewrite` (in `rewriteDefine.c`) only allows RETURNING in
  unconditional INSTEAD rules. See the assertion / comment at
  `rewriteHandler.c:4533`.
- The `EXCLUDED` pseudo-relation of ON CONFLICT is intentionally NOT
  view-expanded, even if it points to a view, to keep the RTE
  `RTE_RELATION`. `:2131-2138`.
- Materialized views are never expanded as if they were views.
  `:2117-2128`.
- Recursion detection in RIR uses `activeRIRs` (list of Oids); recursion
  detection in DML rule application uses `rewrite_events` (Oid + cmdtype
  pairs). They are independent.

## Open question

- The precise interaction between rule-introduced subqueries and RLS is
  subtle: a rule's action query references the target relation; that
  target relation's RLS policies are added during `fireRIRrules` on the
  product query *after* the rule was already substituted. Need to
  confirm by case analysis that this composes correctly when both a
  user-defined INSTEAD rule and an RLS policy exist on the same table.
  [unverified]
