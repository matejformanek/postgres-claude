# Parser pipeline — from SQL text to a Query tree

The path a SQL statement takes from a client buffer to the planner is
fixed and uniform across all statement kinds. Four stages, two parse
trees, one rewriter pass.

```
SQL text
  │
  │  raw_parser()              src/backend/parser/parser.c
  ▼
List<RawStmt>   ──── raw parse tree (flex + bison, no catalog access)
  │
  │  parse_analyze_*()         src/backend/parser/analyze.c
  ▼
Query           ──── analyzed parse tree (catalog-resolved, tagged)
  │
  │  pg_rewrite_query()        src/backend/rewrite/
  ▼
List<Query>     ──── after view expansion + rule application
  │
  │  pg_plan_queries()         src/backend/optimizer/plan/planner.c
  ▼
List<PlannedStmt>
  │
  ▼  executor
```

## Stage 1 — raw parse (flex + bison)

Entry point: `raw_parser(const char *str, RawParseMode mode)` in
`src/backend/parser/parser.c` [verified-by-code: `parser.c:35-42`]. It returns
a `List *` of `RawStmt` nodes — one per semicolon-separated statement.

Under the hood:
- **`scan.l`** is a flex specification producing the tokenizer. Postgres requires
  the scanner to be **no-backtrack** for speed; flex's `-b` mode catches
  regressions in `lex.backup` [from-comment: `scan.l:13-22`]. The same lexical
  rules also live in `src/fe_utils/psqlscan.l` and `src/interfaces/ecpg/preproc/pgc.l`
  and must be kept in sync by hand.
- **`gram.y`** is a bison grammar producing `RawStmt`-rooted trees of parse nodes
  defined in `src/include/nodes/parsenodes.h`. Actions call `makeNode(FooStmt)`
  and fill fields from `$N` token values. Locations are tracked via `@N` and
  end up in `location` fields of the produced nodes.

What's **not** done at this stage:
- No catalog lookup. The parser does not know whether a name is a table, a
  view, or a typo. It does not resolve column references. It does not
  acquire locks.
- No type checking, no operator resolution, no function lookup.

So the raw tree is purely syntactic. The same `SELECT foo FROM bar` produces
the same `RawStmt` whether `bar` exists or not.

### Walking through SELECT

A `SelectStmt` is produced by the `SelectStmt` rule
[verified-by-code: `gram.y:13629-13631`]:

```
SelectStmt: select_no_parens %prec UMINUS
          | select_with_parens %prec UMINUS ;
```

`select_no_parens` then decomposes into `simple_select` plus optional
`sort_clause`, `for_locking_clause`, `select_limit`, `with_clause` —
each variant calling `insertSelectOptions((SelectStmt *) $1, ...)` to
attach the optional pieces onto the same already-built `SelectStmt`
[verified-by-code: `gram.y:13649-13706`]. `simple_select` itself
produces the SELECT-list / FROM / WHERE / GROUP / HAVING shape.

This is the bison idiom you'll reproduce when adding statements: a top
rule that allocates the node, sub-rules that fill or wrap it.

## Stage 2 — parse analysis

Entry point: `parse_analyze_fixedparams(RawStmt *parseTree, ...)` and
friends in `src/backend/parser/analyze.c` [verified-by-code: `analyze.c:127`].
Dispatch is by `nodeTag(parseTree->stmt)` inside `transformStmt`
[verified-by-code: `analyze.c:334-433`]:

```c
switch (nodeTag(parseTree)) {
  case T_InsertStmt: result = transformInsertStmt(pstate, ...); break;
  case T_DeleteStmt: result = transformDeleteStmt(pstate, ...); break;
  case T_UpdateStmt: result = transformUpdateStmt(pstate, ...); break;
  case T_MergeStmt:  result = transformMergeStmt(pstate, ...); break;
  case T_SelectStmt: ... ; break;
  case T_ExplainStmt: ... ;
  ...
  default:                  /* utility */
    result = makeNode(Query);
    result->commandType = CMD_UTILITY;
    result->utilityStmt = (Node *) parseTree;
}
```

The `default` branch is the **utility-statement shortcut**: most DDL
(CREATE TABLE, ALTER, DROP, CREATE INDEX, ...) is *not* analyzed here.
It's wrapped untransformed inside a `Query{commandType=CMD_UTILITY}` and
re-examined at execution time by `parser/parse_utilcmd.c` [from-comment:
`analyze.c:8-14`]. The rationale: utility commands cannot reliably hold
locks across plan-cache boundaries.

For optimizable statements, the per-kind `transformFooStmt` does:
- Resolve table references and acquire appropriate locks (`AccessShareLock`
  for SELECT, `RowExclusiveLock` for the target of INSERT/UPDATE/DELETE/MERGE).
- Build the range table (`Query.rtable`) and the join tree (`Query.jointree`).
- Type-check expressions via `parser/parse_expr.c`, resolve operators via
  `parse_oper.c`, resolve functions via `parse_func.c`.
- Build the target list (`Query.targetList`) of `TargetEntry` nodes.
- Process WHERE / GROUP / HAVING / ORDER BY / LIMIT / WITH clauses via
  the matching `parse_clause.c` / `parse_cte.c` / `parse_agg.c` helpers.

State for the whole transformation lives in `ParseState`, allocated by
`make_parsestate()` [verified-by-code: `parse_node.c:38-50`]. It threads
through every helper so they can look up column references, register
namespace entries, track aggregate-vs-windowfunc context, etc.

Output is a `Query` (defined at `parsenodes.h:120`), which is the contract
between the parser and everything downstream.

The `post_parse_analyze_hook` (`analyze.c:74`) lets extensions like
`pg_stat_statements` see every analyzed query before the rewriter — that's
where the query-id is computed.

## Stage 3 — rewriter

`pg_rewrite_query()` in `src/backend/rewrite/` runs rule actions and
expands views. A view reference in the range table is replaced by the
view's stored `Query` (loaded from `pg_rewrite.ev_action` via
`stringToNode`). RLS policies are injected here. One input `Query`
becomes a `List *` of `Query` (DO INSTEAD rules can multiply or replace
it). [unverified — not read in this pass; check `rewriteHandler.c`.]

## Stage 4 — planner

Each rewritten `Query` is fed to `planner()` (`optimizer/plan/planner.c`),
which produces a `PlannedStmt` wrapping a `Plan` tree. From there the
executor takes over (see `executor-and-planner` skill if/when that lands).

## What changes per statement type

| Statement | Raw node | After analyze |
| --- | --- | --- |
| `SELECT` / `INSERT` / `UPDATE` / `DELETE` / `MERGE` | matching `*Stmt` | full `Query` with `commandType = CMD_SELECT/...` and resolved `rtable` / `targetList` / `jointree` |
| DDL (CREATE/ALTER/DROP/...) | matching `*Stmt` | `Query{commandType=CMD_UTILITY, utilityStmt=original}` — analyzed later inside `ProcessUtility` |
| `EXPLAIN` / `DECLARE CURSOR` / `CREATE TABLE AS` / `CALL` | matching `*Stmt` | special — has its own `transform*Stmt` because the wrapped statement IS optimizable |
| `SET` / `RESET` / transaction control | `VariableSetStmt` / `TransactionStmt` | utility |

The "everything is a Query" funnel is why the rest of the backend can talk
about queries uniformly — plan cache, `pg_stat_statements`, parallel-worker
serialization, rule storage all operate on `Query` (parse) or `PlannedStmt`
(plan) without caring whether the source SQL was DML or DDL.


## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-hook`](../scenarios/add-new-hook.md)
- [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md)
- [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md)

<!-- /scenarios:auto -->
