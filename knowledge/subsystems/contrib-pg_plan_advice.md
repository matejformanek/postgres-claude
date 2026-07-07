# contrib-pg_plan_advice (planner-advice / query-shape hints)

- **Source path:** `source/contrib/pg_plan_advice/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` + ALTER SYSTEM
- **Surface:** SQL-callable hint installation + planner hook

## 1. Purpose

Apply **per-query planner hints** stored in a catalog table
(the "trove"). Lets DBAs nail down specific query shapes —
forcing a particular join order, index usage, or scan method
— without modifying application SQL.

Newer than the rest of contrib (the largest one introduced in
recent PG versions). Substantial — 7 .c files totaling ~5400
LOC [verified-by-code `wc -l`]. The reference for "how do I
hook the planner" extension authors.

## 2. The 7 C files

| File | LOC | What it does |
|---|---|---|
| `pg_plan_advice.c` | 457 | Extension registration + hook |
| `pgpa_planner.c` | 2229 | Plan-rewrite logic |
| `pgpa_join.c` | 642 | Join-order hint application |
| `pgpa_output.c` | 606 | Format produced plan for display |
| `pgpa_trove.c` | 518 | Storage of hints (the "trove") |
| `pgpa_identifier.c` | 481 | Query-shape identification |
| `pgpa_ast.c` | 357 | AST manipulation |
| `pgpa_scan.c` | 289 | Scan-path hint application |

The split reflects clear responsibility separation: a
trove of hints + an identifier matching query → trove key
+ planner hook that applies hints during planning.

## 3. The planner hook

`_PG_init` installs the planner hook
[verified-by-code `pg_plan_advice.c:65`]:

```c
prev_planner_hook = planner_hook;
planner_hook = pgpa_planner_hook;
```

The hook fires before the planner produces a plan. It:

1. Compute a stable identifier for the incoming query.
2. Look up hints in the trove for this identifier.
3. If hints found, modify the planner state to force the
   chosen plan shape.
4. Delegate to `standard_planner` for the actual planning.
5. Validate the produced plan against hints; warn if a
   hint couldn't be applied.

## 4. The query identifier

`pgpa_identifier.c` (481 LOC) implements stable query
identification. A query like:

```sql
SELECT * FROM t WHERE id = 5;
SELECT * FROM t WHERE id = 99;
```

Has the SAME shape — table, columns, predicate type — even
though the literal differs. Both produce the same identifier;
hints attached to one apply to both.

The identifier algorithm normalizes:
- Constants → parameters.
- Schema-qualified vs unqualified relation references.
- Alias-renaming.
- Comment stripping.

## 5. The trove

`pgpa_trove.c` (518 LOC) is the hint storage. Hints live in
a system catalog table; queryable via SQL functions provided
by the extension. The trove API supports:

- **Install hint** for a query identifier.
- **Remove hint** by identifier.
- **List hints** in scope.
- **Query for hint** during planning (the planner hook's
  primary call).

## 6. Hint types

`pgpa_join.c` and `pgpa_scan.c` implement two hint
categories:

- **Join hints**: "use hash join here", "join order ABC",
  "join algorithm bitmap heap scan + nested loop".
- **Scan hints**: "use this index", "force seq scan",
  "force index-only scan".

The planner hook translates hints into the planner's
internal flags (`enable_seqscan = false` for that subquery,
`from_collapse_limit` adjustments, etc.).

## 7. The validation pass

After `standard_planner` returns, the extension's output
formatter (`pgpa_output.c`, 606 LOC) checks the produced
plan against the requested hints. If a hint couldn't be
applied (e.g., the hinted index doesn't exist), it WARNs.

This is critical user-feedback: silently ignoring hints would
make pg_plan_advice useless. WARN forces the DBA to fix the
hint.

## 8. The AST manipulation layer

`pgpa_ast.c` (357 LOC) walks the parsed `Query` tree to
identify the hint-targetable subqueries. The planner hook
sees a `Query *`; the AST helper walks it to find the
sites where hints apply.

Useful for extension authors learning the planner: this is
"how to read a Query tree" reference code.

## 9. Production-use guidance

- **Test hints before relying on them.** Hint quality varies
  by data distribution.
- **Audit which queries have hints** regularly — schema
  changes can make hints stale.
- **Prefer schema design + statistics over hints** when
  possible. Hints are a workaround, not a fix.
- **For one-off slow queries**, hint may be fastest fix.
- **For systematic planner issues**, work with the upstream
  community to improve the planner.

## 10. Invariants

- **[INV-1]** Hints are matched by query identifier (stable
  hash of query shape).
- **[INV-2]** Constants normalized to params for matching;
  same shape → same identifier.
- **[INV-3]** Validation pass WARNs if hint not applied.
- **[INV-4]** Hook chains via `prev_planner_hook`.
- **[INV-5]** Loaded via `shared_preload_libraries`; hints
  in a catalog table.

## 11. Useful greps

- The planner hook:
  `grep -n 'planner_hook\|pgpa_planner_hook' source/contrib/pg_plan_advice/pg_plan_advice.c`
- The identifier algorithm:
  `grep -n 'pgpa_identifier_for_query\|hash_query' source/contrib/pg_plan_advice/pgpa_identifier.c | head -10`
- The trove API:
  `grep -n 'pgpa_trove_' source/contrib/pg_plan_advice/pgpa_trove.c | head -10`

## 12. Cross-references

- `knowledge/subsystems/optimizer.md` — the planner this
  hooks into.
- `.claude/skills/executor-and-planner/SKILL.md` —
  planner_hook + standard_planner contract.
- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  shared_preload_libraries loading + hook installation.
- `knowledge/subsystems/contrib-pg_overexplain.md` —
  companion EXPLAIN-extending contrib; complementary view
  into planner state.
- `source/contrib/pg_plan_advice/` — implementation directory.
- `source/src/include/optimizer/planner.h` — planner_hook
  declaration.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**18 files.**

| File |
|---|
| [`contrib/pg_plan_advice/pg_plan_advice.c`](../files/contrib/pg_plan_advice/pg_plan_advice.c.md) |
| [`contrib/pg_plan_advice/pg_plan_advice.h`](../files/contrib/pg_plan_advice/pg_plan_advice.h.md) |
| [`contrib/pg_plan_advice/pgpa_ast.c`](../files/contrib/pg_plan_advice/pgpa_ast.c.md) |
| [`contrib/pg_plan_advice/pgpa_ast.h`](../files/contrib/pg_plan_advice/pgpa_ast.h.md) |
| [`contrib/pg_plan_advice/pgpa_identifier.c`](../files/contrib/pg_plan_advice/pgpa_identifier.c.md) |
| [`contrib/pg_plan_advice/pgpa_identifier.h`](../files/contrib/pg_plan_advice/pgpa_identifier.h.md) |
| [`contrib/pg_plan_advice/pgpa_join.c`](../files/contrib/pg_plan_advice/pgpa_join.c.md) |
| [`contrib/pg_plan_advice/pgpa_join.h`](../files/contrib/pg_plan_advice/pgpa_join.h.md) |
| [`contrib/pg_plan_advice/pgpa_output.c`](../files/contrib/pg_plan_advice/pgpa_output.c.md) |
| [`contrib/pg_plan_advice/pgpa_output.h`](../files/contrib/pg_plan_advice/pgpa_output.h.md) |
| [`contrib/pg_plan_advice/pgpa_planner.c`](../files/contrib/pg_plan_advice/pgpa_planner.c.md) |
| [`contrib/pg_plan_advice/pgpa_planner.h`](../files/contrib/pg_plan_advice/pgpa_planner.h.md) |
| [`contrib/pg_plan_advice/pgpa_scan.c`](../files/contrib/pg_plan_advice/pgpa_scan.c.md) |
| [`contrib/pg_plan_advice/pgpa_scan.h`](../files/contrib/pg_plan_advice/pgpa_scan.h.md) |
| [`contrib/pg_plan_advice/pgpa_trove.c`](../files/contrib/pg_plan_advice/pgpa_trove.c.md) |
| [`contrib/pg_plan_advice/pgpa_trove.h`](../files/contrib/pg_plan_advice/pgpa_trove.h.md) |
| [`contrib/pg_plan_advice/pgpa_walker.c`](../files/contrib/pg_plan_advice/pgpa_walker.c.md) |
| [`contrib/pg_plan_advice/pgpa_walker.h`](../files/contrib/pg_plan_advice/pgpa_walker.h.md) |

<!-- /files-owned:auto -->
