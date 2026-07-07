# Subsystem: parser + rewrite

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Peter Eisentraut (51), Tom Lane (36), Álvaro Herrera (20), Michael Paquier (15)
- **Top reviewers (last 24mo):** Jian He (24), Peter Eisentraut (14), Álvaro Herrera (14), Tom Lane (13)
- **Recent landmark commits (12mo):**
  - `81ce602d48e (Fujii Masao, 2025-06-26): Make CREATE TABLE LIKE copy comments on NOT NULL constraints when requested.`
  - `5548a969b65 (Dean Rasheed, 2026-04-22): Fix UPDATE/DELETE ... WHERE CURRENT OF on a table with virtual columns.`
  - `487cf2cbd2f (Andrew Dunstan, 2026-03-12): Extend DomainHasConstraints() to optionally check constraint volatility`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Paths:** `source/src/backend/parser/`, `source/src/backend/rewrite/`,
  `source/src/include/parser/`, `source/src/include/rewrite/`
- **Verified against commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
  (2026-06-01 refresh anchor — same content as `ef6a95c7c64` for these dirs)
- **Confidence:** verified=58, from-README=5, from-comment=24, inferred=4,
  unverified=3 (Open Questions §9)
- **Primary README:** `source/src/backend/parser/README` (36 lines, lists every
  `parse_*.c` and its role). `rewrite/` has **no README**; the canonical
  narrative lives in the file headers of `rewriteHandler.c` and
  `rewriteDefine.c`.

## 1. Purpose

The parser turns a SQL text buffer into an analyzed `Query` tree. The rewriter
takes that `Query`, applies stored rules (`pg_rewrite`), expands views, injects
Row-Level Security policy quals, lowers SEARCH/CYCLE CTE clauses and
`GRAPH_TABLE`, and returns a `List<Query>` — the contract the planner
consumes. Conceptually they're two stages of the same pipeline:

```
SQL text → raw parse → parse analyse → rewrite → planner
           parser.c    analyze.c       rewriteHandler.c
           gram.y      parse_*.c       rewriteManip.c
           scan.l                      rowsecurity.c
```

[See `knowledge/idioms/parser-pipeline.md` for the end-to-end walk-through —
this doc is the directory-level deep-dive.] [via
`knowledge/idioms/parser-pipeline.md`]

The split is structural, not optional:

- **Raw parse must run with no catalog access and survive aborted transactions.**
  `gram.y:23-25` mandates it. So no name resolution, no type checking, no
  locks. [from-comment] `gram.y:23-25`
- **Parse-analyze is the first catalog-touching pass.** It acquires locks
  (recorded on each `RangeTblEntry`), resolves columns/functions/operators,
  types every expression. Lock acquisition here is load-bearing for the
  rewriter's `AcquireRewriteLocks` re-acquisition logic later
  [verified-by-code] `rewriteHandler.c:148`.
- **Rewrite is the *second* post-parser pass.** It's where views become
  subqueries, RLS becomes WHERE-clause quals, and DO INSTEAD rules can
  multiply / replace queries. [from-comment] `rewriteHandler.c:3-19`

The two directories total ~71 KB of `.c` (parser/) + ~336 KB (rewrite/, most
of it `rewriteHandler.c` at 152 KB). All per-file docs exist under
`knowledge/files/src/backend/{parser,rewrite}/...` — this synthesis cites the
spine.

## 2. Key files

### parser/ (25 .c files)

| File | Role | Per-file doc |
|---|---|---|
| `parser.c` | Driver: `raw_parser()` wraps flex+bison; `base_yylex()` is the multi-token lookahead filter | [via `knowledge/files/src/backend/parser/parser.c.md`] |
| `scan.l` | Flex spec → `core_yylex()`. Must stay no-backtrack (Makefile checks `lex.backup` is empty since PG 9.2) | [via `knowledge/files/src/backend/parser/scan.l.md`] |
| `scansup.c` | Escape handling for string literals | [via `knowledge/files/src/backend/parser/scansup.c.md`] |
| `gram.y` | 524 KB bison grammar; produces a `List<RawStmt>` | [via `knowledge/files/src/backend/parser/gram.y.md`] |
| `analyze.c` | Top of parse analysis. `parse_analyze_*` entry points + `transformStmt` dispatcher | [via `knowledge/files/src/backend/parser/analyze.c.md`] |
| `parse_node.c` | `ParseState` lifecycle + small node-makers (`make_var`, `make_const`) | [via `knowledge/files/src/backend/parser/parse_node.c.md`] |
| `parse_clause.c` | FROM/JOIN/WHERE/GROUP/HAVING/ORDER/LIMIT/WINDOW/DISTINCT, ON CONFLICT inference | [via `knowledge/files/src/backend/parser/parse_clause.c.md`] |
| `parse_expr.c` | Per-node expression transformer (`A_Expr` → `OpExpr`, `ColumnRef` → `Var`, …) | [via `knowledge/files/src/backend/parser/parse_expr.c.md`] |
| `parse_relation.c` | Namespace lookup + RTE construction + fuzzy-match diagnostics + `*`-expansion machinery | [via `knowledge/files/src/backend/parser/parse_relation.c.md`] |
| `parse_target.c` | Target-list build (`TargetEntry`); `FigureColname`; subscripted assignment | [via `knowledge/files/src/backend/parser/parse_target.c.md`] |
| `parse_func.c` | Function-call resolution incl. agg/window/proc routing | [via `knowledge/files/src/backend/parser/parse_func.c.md`] |
| `parse_oper.c` | Operator resolution with a process-local `OprCache` | [via `knowledge/files/src/backend/parser/parse_oper.c.md`] |
| `parse_coerce.c` | Type-coercion engine; legality + node construction (`RelabelType`/`CoerceViaIO`/`ArrayCoerceExpr`/…) | [via `knowledge/files/src/backend/parser/parse_coerce.c.md`] |
| `parse_collate.c` | Post-pass: assign output + function collations to expressions | [via `knowledge/files/src/backend/parser/parse_collate.c.md`] |
| `parse_agg.c` | Aggregate / window-func validation + post-pass GROUP-BY sanity check | [via `knowledge/files/src/backend/parser/parse_agg.c.md`] |
| `parse_type.c` | `TypeName` → `Oid` resolution | [via `knowledge/files/src/backend/parser/parse_type.c.md`] |
| `parse_cte.c` | WITH clause: per-CTE sub-analyze, recursion detection (Tarjan SCC), `MATERIALIZED` hint | [via `knowledge/files/src/backend/parser/parse_cte.c.md`] |
| `parse_merge.c` | `MERGE` statement parse analysis | [via `knowledge/files/src/backend/parser/parse_merge.c.md`] |
| `parse_param.c` | `$n` `ParamRef` resolution for the two core-backend cases (fixed types, deduced types) | [via `knowledge/files/src/backend/parser/parse_param.c.md`] |
| `parse_enr.c` | Ephemeral named rels (trigger transition tables) | [via `knowledge/files/src/backend/parser/parse_enr.c.md`] |
| `parse_jsontable.c` | `JSON_TABLE()` | [via `knowledge/files/src/backend/parser/parse_jsontable.c.md`] |
| `parse_graphtable.c` | `GRAPH_TABLE()` (PG 18) | [via `knowledge/files/src/backend/parser/parse_graphtable.c.md`] |
| `parse_utilcmd.c` | **Deferred** parse analysis for DDL — runs at `ProcessUtility` time, not at the original `parse_analyze` | [via `knowledge/files/src/backend/parser/parse_utilcmd.c.md`] |

### rewrite/ (8 .c files; no README)

| File | Role | Per-file doc |
|---|---|---|
| `rewriteHandler.c` | The rewriter itself. `QueryRewrite` is the top entry; everything else in the directory hangs off it | [via `knowledge/files/src/backend/rewrite/rewriteHandler.c.md`] |
| `rewriteManip.c` | Tree-manipulation library: `OffsetVarNodes`, `ChangeVarNodes`, `IncrementVarSublevelsUp`, `ReplaceVarsFromTargetList`, `AddQual`, `AddInvertedQual` | [via `knowledge/files/src/backend/rewrite/rewriteManip.c.md`] |
| `rewriteDefine.c` | `CREATE RULE` + the `_RETURN` rule that backs every view. `DefineQueryRewrite` is shared with `commands/view.c` | [via `knowledge/files/src/backend/rewrite/rewriteDefine.c.md`] |
| `rewriteRemove.c` | `DROP RULE` | [via `knowledge/files/src/backend/rewrite/rewriteRemove.c.md`] |
| `rewriteSupport.c` | Tiny shared helpers: `IsDefinedRewriteRule`, `SetRelationRuleStatus` | [via `knowledge/files/src/backend/rewrite/rewriteSupport.c.md`] |
| `rewriteSearchCycle.c` | Expand recursive-CTE `SEARCH` / `CYCLE` clauses into ordering columns + cycle-detect arrays | [via `knowledge/files/src/backend/rewrite/rewriteSearchCycle.c.md`] |
| `rewriteGraphTable.c` | Lower `GRAPH_TABLE` RTEs into `RTE_SUBQUERY` | [via `knowledge/files/src/backend/rewrite/rewriteGraphTable.c.md`] |
| `rowsecurity.c` | Row-Level Security: fetch policies for an RTE; produce qual + with-check expressions | [via `knowledge/files/src/backend/rewrite/rowsecurity.c.md`] |

### Header anchors

| Header | What it defines |
|---|---|
| `src/include/nodes/parsenodes.h` | `RawStmt` (`:2187`), `Query` (`:117`), `RangeTblEntry` (`:1137`), `CmdType`, `QuerySource` (`:34`), `TargetEntry`, `RangeTblFunction`, all the `*Stmt` raw nodes |
| `src/include/parser/parse_node.h` | `ParseState`, `ParseExprKind` enum (38 values) |
| `src/include/parser/parser.h` | `RawParseMode` enum; `raw_parser` prototype |
| `src/include/parser/parsetree.h` | `rt_fetch`-family inline helpers (the only file allowed to read positionally into `Query.rtable`) |
| `src/include/parser/gramparse.h` | `base_yy_extra_type`; shared scanner/parser state |
| `src/include/rewrite/rewriteHandler.h` | `QueryRewrite`, `AcquireRewriteLocks` |
| `src/include/rewrite/rewriteManip.h` | The Var-manipulation toolkit (see §4) |
| `src/include/rewrite/rowsecurity.h` | `get_row_security_policies` + the `WCO_RLS_*` `WithCheckOption` kinds |

## 3. Key data structures

### `RawStmt` — the raw-parse tree root

```c
typedef struct RawStmt {
    NodeTag    type;
    Node      *stmt;           /* raw parse tree */
    ParseLoc   stmt_location;  /* start position in source text */
    ParseLoc   stmt_len;       /* length; 0 if to-end-of-string */
} RawStmt;
```
[verified-by-code] `parsenodes.h:2187`. One per semicolon-separated statement;
`raw_parser()` returns a `List<RawStmt>`. Only `parser.c` constructs these.

### `Query` — the analyzed parse tree

The contract between parser and the rest of the backend (rewriter, plancache,
planner, `pg_stat_statements`, parallel-worker serialization). Defined at
`parsenodes.h:117`. The most load-bearing fields:

- `commandType` (`CmdType`) — `CMD_SELECT` / `INSERT` / `UPDATE` / `DELETE` /
  `MERGE` / `UTILITY`. Drives the dispatcher in `rewriteHandler.c:RewriteQuery`
  and in `tcop/pquery.c`.
- `querySource` (`QuerySource`, enum at `parsenodes.h:34`) — `QSRC_ORIGINAL`
  for parser output, `QSRC_INSTEAD_RULE` / `QSRC_QUAL_INSTEAD_RULE` /
  `QSRC_NON_INSTEAD_RULE` for queries produced by rewriting. `QueryRewrite`
  asserts the top-level input is `QSRC_ORIGINAL` [verified-by-code]
  `rewriteHandler.c:4794-4795`.
- `canSetTag` — exactly one Query in the rewritten list should carry the
  command tag. The Step-3 adjustment in `QueryRewrite` enforces this; see §4.
- `utilityStmt` — non-NULL iff `commandType == CMD_UTILITY`; holds the
  untransformed raw stmt.
- `rtable` (`List<RangeTblEntry>`) + `rteperminfos` (`List<RTEPermissionInfo>`)
  + `jointree` (`FromExpr` with `quals` = WHERE) — the FROM/WHERE shape.
- `targetList` (`List<TargetEntry>`) — the SELECT-list / RETURNING / SET RHS.
- `groupClause` / `groupingSets` / `havingQual` / `windowClause` /
  `distinctClause` / `sortClause` / `limitOffset` / `limitCount` /
  `limitOption` / `rowMarks` — the rest of the SELECT shape.
- `cteList` — WITH clauses (each is a `CommonTableExpr`).
- `mergeActionList` (for MERGE) — list of `MergeAction` nodes, one per `WHEN`.
- `hasAggs`, `hasWindowFuncs`, `hasTargetSRFs`, `hasSubLinks`, `hasDistinctOn`,
  `hasRecursive`, `hasModifyingCTE`, `hasForUpdate`, `hasRowSecurity` —
  feature bits the planner consults for fast-path decisions.
- `stmt_location` / `stmt_len` — copied from `RawStmt`. `pg_stat_statements`
  needs them to slice the source text for each statement when the cache key
  is the jumbled queryId.

### `RangeTblEntry` — what's in the range table

[verified-by-code] `parsenodes.h:1137`. Discriminated union via the
`RTEKind` enum:

`RTE_RELATION` (table/MV/view/foreign-table/partitioned-table), `RTE_SUBQUERY`,
`RTE_JOIN` (synthesized USING-merge alias holder), `RTE_FUNCTION`,
`RTE_TABLEFUNC` (XMLTABLE/JSON_TABLE), `RTE_VALUES` (multi-row VALUES),
`RTE_CTE`, `RTE_NAMEDTUPLESTORE` (transition tables — ephemeral named rel),
`RTE_RESULT` (degenerate single-row source for FROM-less SELECTs after
rewriting), `RTE_GRAPH_TABLE` (PG 18).

Per-RTE bookkeeping:
- `rellockmode` — the AccessShareLock / RowShareLock / RowExclusiveLock /
  AccessExclusiveLock that the parser took. `AcquireRewriteLocks` (see §4)
  re-takes these for stored/cached queries.
- `eref` (always) and `alias` (optional) — column names for diagnostics +
  `SELECT *` expansion.
- `lateral`, `inFromCl`, `inh` (inheritance flag), `requiredPerms` (now moved
  to a sibling `RTEPermissionInfo` list, per PG 16+).

### `ParseState` — the parser's scratchpad

[verified-by-code] `parse_node.h:91`. Threaded through every helper.

- `p_sourcetext` — for `ereport`'s cursor.
- `p_rtable` / `p_joinlist` / `p_namespace` — building blocks for the
  eventual `Query`. `p_namespace` is the list of `ParseNamespaceItem`s
  visible *right now* (mutated as we walk the join tree).
- `p_parent_parsestate` + `p_locked_from_parent` + `p_resolve_unknowns` —
  for sub-statement recursion (`parse_sub_analyze`).
- `p_paramref_hook` / `p_coerce_param_hook` / `p_pre_columnref_hook` /
  `p_post_columnref_hook` — extension points. PL/pgSQL uses them to
  resolve `$N` to PL/pgSQL variables; `parse_param.c` uses them for
  fixed/variable protocol parameters [via
  `knowledge/files/src/backend/parser/parse_param.c.md`].
- `p_expr_kind` — current `ParseExprKind` (38-value enum). Drives
  context-specific error wording AND feature gating (window funcs are
  legal in `EXPR_KIND_SELECT_TARGET` but not `EXPR_KIND_WHERE`).
- `p_target_relation` / `p_target_nsitem` — the result rel for
  UPDATE/INSERT/DELETE/MERGE.
- `p_hasAggs` / `p_hasWindowFuncs` / `p_hasTargetSRFs` / `p_hasSubLinks` —
  feature bits eventually copied into the `Query`.
- `p_next_resno` — monotonic counter feeding `TargetEntry.resno`.

`make_parsestate(NULL)` allocates a top-level pstate; sub-statements use
`make_parsestate(parent)` so column resolution can walk up
`p_parent_parsestate` for outer-query Var refs (driving `Var.varlevelsup`).
[verified-by-code] `parse_node.c`. `free_parsestate` releases the held
`p_target_relation` — forgetting it leaks a relcache pin.

### `RewriteRule` — the in-memory form of a `pg_rewrite` row

Loaded into the relcache from `pg_rewrite.ev_action` (string-encoded via
`nodeToString`) at relation-open time and stored on the `Relation`.
`matchLocks` `rewriteHandler.c:1687` looks them up by event + relation +
enabling state. The columns are:

- `event` (`CmdType`) — SELECT / INSERT / UPDATE / DELETE.
- `attrno` — column the rule fires for (only used by historic per-column
  rules; nearly always `InvalidAttrNumber`).
- `qual` — the `WHERE` clause (may be NIL = unconditional).
- `actions` — `List<Query>` of rule body queries.
- `isInstead`, `enabled` — rule modifier flags.

[See `knowledge/files/src/backend/rewrite/rewriteDefine.c.md` for the
`pg_rewrite` schema and the on-disk shape.]

### `CommonTableExpr` — a WITH-clause CTE

Carries the unanalyzed body (`ctequery` before, `Query *` after
`parse_cte.c:analyzeCTE`) plus the resolved `ctecolnames` / `ctecoltypes` /
`ctecoltypmods` / `ctecolcollations`. `cterecursive` is set by the parser's
recursion check (Tarjan SCC in `parse_cte.c`); `cterefcount` is incremented
each time the planner needs to inline. `search_clause` / `cycle_clause` are
*not* expanded by `parse_cte.c` — they live on the CTE node until
`rewriteSearchCycle.c` lowers them inside `fireRIRrules`. [verified-by-code]
`rewriteHandler.c:2049-2063`.

### `TargetEntry` — a single output / assignment slot

Each entry carries `expr`, `resno` (1-based, assigned via
`pstate->p_next_resno++`), `resname` (`AS x` or `FigureColname` default),
`resjunk` (true = sort/group only, dropped by executor projection but kept
by planner), `resorigtbl` / `resorigcol` (for bare-Var SELECT output, drives
`\d`-style introspection). The `resjunk` invariant is the easy-to-miss one
— the planner happily ships them downstream if you forget to set it. [via
`knowledge/files/src/backend/parser/parse_target.c.md`]

## 4. Core algorithms / control flow

### Stage 1 — raw parse

```
raw_parser(str, mode)                              parser.c:42
  ├─ scanner_init(str, &yyextra, ...)              scan.l → core_yylex
  ├─ parser_init(&yyextra)                         gram.y prologue
  ├─ base_yyparse(yyscanner)                       gram.c (built from gram.y)
  │     │
  │     └─ token stream filtered by base_yylex     parser.c:111
  │         (FORMAT JSON, NOT BETWEEN, NULLS FIRST/LAST,
  │          WITH TIME ZONE, UIDENT→IDENT, USCONST→SCONST …)
  └─ return yyextra->parsetree                     List<RawStmt>
```

[verified-by-code] `parser.c:42-108`. Lookahead lives in `base_yylex` so the
grammar can stay LALR(1) and the lexer can stay no-backtrack [from-comment]
`scan.l:13-22`.

`RawParseMode` (`parser.c:53-71`) lets PL/pgSQL reuse the grammar via an
injected pseudo-start token (`MODE_TYPE_NAME`, `MODE_PLPGSQL_EXPR`, etc.).

### Stage 2 — parse analysis (`analyze.c`)

```
parse_analyze_fixedparams / _varparams / _withcb     analyze.c:127, :167, :208
  ├─ make_parsestate(NULL)                            parse_node.c
  ├─ setup_parse_fixed_parameters | _variable        parse_param.c
  ├─ transformTopLevelStmt(pstate, parseTree)        analyze.c:271
  │   └─ transformOptionalSelectInto                 analyze.c:294-327
  │       (rewrites top-level `SELECT INTO t` → `CreateTableAsStmt`)
  │   └─ transformStmt(pstate, parseTree)            analyze.c:334
  │       switch (nodeTag) → transformInsertStmt / DeleteStmt /
  │                          UpdateStmt / MergeStmt / SelectStmt /
  │                          ReturnStmt / PLAssignStmt / DeclareCursorStmt /
  │                          ExplainStmt / CreateTableAsStmt / CallStmt
  │                          default: Query{CMD_UTILITY, utilityStmt=raw}
  ├─ if (IsQueryIdEnabled()) JumbleQuery(query)      queryjumble.c
  ├─ if (post_parse_analyze_hook) hook(pstate, q, j) analyze.c:74
  └─ free_parsestate(pstate); return query
```

[verified-by-code] `analyze.c:127-241, :334-444`.

Per-statement transformers below the dispatcher all share the same overall
shape: build RTEs (via `addRangeTableEntry*` in `parse_relation.c`), build
the jointree (`transformFromClause` in `parse_clause.c`), build the target
list (`transformTargetList` in `parse_target.c`), type-check WHERE / HAVING /
ON quals (`coerce_to_boolean` in `parse_coerce.c`), then run the
`parse_collate.c` post-pass and the `parse_agg.c:parseCheckAggregates`
post-pass.

The three `parse_analyze_*` entry points differ only in *how* `$n` parameters
are typed:

- `parse_analyze_fixedparams` — types known up-front (cached `PREPARE`).
- `parse_analyze_varparams` — types deduced, the deduced array can grow
  (legacy protocol).
- `parse_analyze_withcb` — caller supplies its own resolver (PL/pgSQL).

All three install a hook on `pstate->p_paramref_hook` and the dispatcher
calls `transformParamRef` via that hook from `parse_expr.c`. [verified-by-code]
`parse_param.c`, `parse_expr.c`.

**The three-sites-change rule.** The `Caution` comment at `analyze.c:363-367`
says: when adding a new optimizable statement node, three sites must change
together — the switch in `transformStmt`, the list in
`stmt_requires_parse_analysis()` (`:469`), and the list in
`analyze_requires_snapshot()` (`:513`). Plancache and tcop use those
predicates to decide whether re-analysis / snapshot acquisition is needed.
[verified-by-code] `analyze.c:363-444, :469-529`.

### Stage 3 — rewrite (`QueryRewrite`)

[verified-by-code] `rewriteHandler.c:4781-…`.

```
QueryRewrite(Query *parsetree)
  Assert(querySource == QSRC_ORIGINAL && canSetTag);
  ├─ Step 1: querylist = RewriteQuery(parsetree, NIL, 0)
  │   └─ non-SELECT rules + DML target-list filling
  ├─ Step 2: for each q in querylist:
  │           q = fireRIRrules(q, NIL)
  │   └─ view expansion + RLS + SEARCH/CYCLE + GRAPH_TABLE
  └─ Step 3: re-assign canSetTag among results
            (original keeps it; else last INSTEAD whose commandType
             matches the original's gets promoted)
```

#### Step 1 — `RewriteQuery` `rewriteHandler.c:4044`

Walks DML targets and applies stored rules:

1. **Process WITH-clause data-modifying CTEs first** by recursively calling
   `RewriteQuery`. Avoid re-rewriting already-processed CTEs in product
   queries via the `num_ctes_processed` counter. [verified-by-code]
   `rewriteHandler.c:4067-4141`.

2. **If the statement is INSERT/UPDATE/DELETE/MERGE,** adjust the target list
   (`rewriteTargetListIU` `:823` fills missing columns with defaults,
   processes generated columns, processes ON CONFLICT DO UPDATE SET lists)
   then fire matching rules via `fireRules` `:2484`.

3. **SELECT statements are NOT rewritten here** — their RIR rules / view
   expansion happen in Step 2 via `fireRIRrules`. The comment at
   `rewriteHandler.c:4147-4149` is explicit.

`fireRules` partitions matching rules into three buckets:

- **Unconditional INSTEAD** → replace the original query entirely.
- **Conditional INSTEAD** → produce a product query plus a modified original
  whose qual is the negation (`qual_product` pattern; `AddInvertedQual` from
  `rewriteManip.c`).
- **Non-INSTEAD ("DO ALSO")** → produce additional product queries alongside
  the original.

Each product query is then recursively passed back into `RewriteQuery`.
Infinite-recursion detection uses the `rewrite_events` list keyed on
`(relation_oid, cmdtype)` pairs. [verified-by-code]
`rewriteHandler.c:4519`.

#### Step 2 — `fireRIRrules` `rewriteHandler.c:2042`

Per-Query walker that does **four ordered things**, and the ordering is
load-bearing:

1. **Expand SEARCH/CYCLE clauses in CTEs.** Convenient hook; not rule-related.
   Calls `rewriteSearchAndCycle` (`rewriteSearchCycle.c`).
   [verified-by-code] `rewriteHandler.c:2049-2063`.

2. **Per-RTE view expansion** by walking `rtable`:
   - Lower `RTE_GRAPH_TABLE` to `RTE_SUBQUERY` via `rewriteGraphTable`
     (`rewriteHandler.c:2088-2091`).
   - Recurse into `RTE_SUBQUERY` RTEs (`:2098-2109`).
   - For `RTE_RELATION` RTEs that aren't materialized views or the
     `EXCLUDED` pseudo-rel of ON CONFLICT, collect RIR (ON SELECT) rules
     and apply them via `ApplyRetrieveRule` (`:2200-2204`).
   - Recursion-loop check via `activeRIRs` list of Oids (`:2189-2194`).

3. **Recurse into CTE bodies and SubLink subqueries** (`:2215-2248`).
   Propagates `hasRowSecurity` upward as it goes.

4. **Apply RLS policies LAST.** [from-comment] `rewriteHandler.c:2249-2255`
   explains why: RLS policy quals may carry sublinks of their own; doing
   RLS inside the loop above would make `query_tree_walker` recurse into
   the quals a second time. So `get_row_security_policies`
   (`rowsecurity.c`) runs after view expansion and after sublink recursion.

#### Step 3 — `canSetTag` adjustment `rewriteHandler.c:4838-4867`

If the original query survives the rewrite, it keeps `canSetTag`. Otherwise
the *last* INSTEAD query whose command type matches the original's command
type is promoted. May leave nobody with the tag — tcop fabricates a default
in that case (see `tcop/cmdtag.c` and the portal-runner in
`tcop/pquery.c`).

### Stage 3a — `AcquireRewriteLocks` `rewriteHandler.c:148`

Any Query that didn't come straight from the parser (`pg_rewrite` rule
bodies via `stringToNode`, view bodies, plancache entries) has *stale* RTE
state: the locks the parser took when first analyzing the query are not
held by the current backend. `AcquireRewriteLocks` is the **first** thing
that runs on such a Query — it re-acquires `rellockmode` per RTE and
fixes up join-RTE alias-Var references to since-dropped columns (replaces
them with null pointers). [verified-by-code] `rewriteHandler.c:103-146`.

Parser output **does not need this step** — locks were just taken by
`parse_relation.c:addRangeTableEntry`. The function header makes the
contract explicit.

### Var-renumbering — the central trick of rule processing

`rewriteManip.c` is the toolkit. The primary operation — "splice a rule
action's tree into the original query" — boils down to:

1. **Append** the rule action's `rtable` to the original's `rtable`.
2. **Shift** the action's `Var.varno`s by the old rtable length
   (`OffsetVarNodes`).
3. **Shift** `varlevelsup` if crossing a subquery boundary
   (`IncrementVarSublevelsUp`).
4. **Substitute** references to the rule's pseudo-RTE (`NEW`/`OLD`) with
   the actual expressions from the action's targetlist
   (`ReplaceVarsFromTargetList`).

The same toolkit is reused outside the rewriter — `planner` calls
`ChangeVarNodes` during set-op planning, partitioning uses
`OffsetVarNodes` when expanding partition children.

## 5. Invariants

- INV-parser-1: **No catalog access in `gram.y`.** `gram.y:23-25` mandates the
  grammar must be able to run in an aborted transaction. Lookups are
  impossible at this stage. [from-comment] `gram.y:23-25`.
- INV-parser-2: **Scanner is no-backtrack.** Flex `-b` mode produces
  `lex.backup`; the Makefile fails the build if it's non-empty. Backtracking
  costs several percent on raw parsing. [from-comment] `scan.l:13-22`.
- INV-parser-3: **`scan.l` kept in sync by hand with `psqlscan.l` and
  ecpg's `pgc.l`.** No code-gen tooling enforces this — the header comment
  is the contract. [from-comment] `scan.l:9-11`.
- INV-parser-4: **Locks are taken at RTE construction** (in
  `parse_relation.c`) at the `rellockmode` recorded on the RTE. Any later
  consumer of the Query (rewriter / plancache / executor) must re-acquire
  via `AcquireRewriteLocks` or its equivalent before reading catalog state.
  [verified-by-code] `rewriteHandler.c:103-146`.
- INV-parser-5: **DDL is not analyzed at parse-analyze time.** The default
  branch in `transformStmt` wraps it in `Query{CMD_UTILITY, utilityStmt}`;
  real analysis is deferred to `ProcessUtility` time via `parse_utilcmd.c`.
  Three reasons stated in `parse_utilcmd.c:6-12`: plan-cache staleness,
  inability to hold locks across the gap, and absence of plan-validity
  rechecks. [from-comment] `parse_utilcmd.c:6-12`, `analyze.c:8-14`.
- INV-parser-6: **The three-sites rule.** Adding an optimizable-statement
  node type requires changes to (a) the switch in `transformStmt`, (b)
  `stmt_requires_parse_analysis()`, (c) `analyze_requires_snapshot()`.
  Skipping any of the three leaves plancache silently wrong.
  [from-comment] `analyze.c:363-367`.
- INV-parser-7: **`assign_query_collations` is a separate post-pass** because
  tracking collation on-the-fly during expression build would require
  permanent extra fields on every parse-node; doing it in a recursive walk
  lets state live in local variables. [from-comment]
  `parse_collate.c:5-12`.
- INV-rewrite-1: **`QueryRewrite` input must be `QSRC_ORIGINAL` with
  `canSetTag=true`.** Enforced by Assert at `rewriteHandler.c:4794-4795`.
  Caller (typically `pg_rewrite_query` in tcop/plancache) guarantees this.
  [verified-by-code] `rewriteHandler.c:4794-4795`.
- INV-rewrite-2: **DML rules fire before view expansion.** `RewriteQuery`
  handles non-SELECT events; SELECT/view expansion is in `fireRIRrules`.
  [from-comment] `rewriteHandler.c:4147-4149`.
- INV-rewrite-3: **RLS is applied LAST inside `fireRIRrules`,** after view
  expansion and after recursion into sublinks/CTEs. The reason — sublink
  double-recursion avoidance — is at `rewriteHandler.c:2249-2255`.
  [from-comment] `rewriteHandler.c:2249-2255`.
- INV-rewrite-4: **WITH-clause data-modifying CTEs are rewritten BEFORE the
  outer statement,** because rule actions on the outer statement may copy
  the WITH clauses into product queries. [from-comment]
  `rewriteHandler.c:4055-4066`.
- INV-rewrite-5: **`AcquireRewriteLocks` is the FIRST step for any non-fresh
  Query.** Skipping it can let schema changes mid-rewrite break things.
  [from-comment] `rewriteHandler.c:128-133`.
- INV-rewrite-6: **The `EXCLUDED` pseudo-rel of ON CONFLICT is NOT view-
  expanded,** even if it points to a view, to keep the RTE `RTE_RELATION`.
  [verified-by-code] `rewriteHandler.c:2131-2138`.
- INV-rewrite-7: **Materialized views are never expanded as views.**
  [verified-by-code] `rewriteHandler.c:2117-2128`.
- INV-rewrite-8: **Recursion detection differs between DML and RIR.** RIR
  uses `activeRIRs` (list of Oids); DML rule application uses
  `rewrite_events` (Oid + cmdtype pairs). They are independent.
  [verified-by-code] `rewriteHandler.c:2189-2194, :4519`.
- INV-rewrite-9: **`DefineQueryRewrite` allows RETURNING only in
  unconditional INSTEAD rules.** Asserted/checked at the call site.
  [verified-by-code] `rewriteHandler.c:4533`, `rewriteDefine.c`.
- INV-rewrite-10: **Every view is implemented as a `_RETURN` unconditional
  INSTEAD ON SELECT rule.** `DefineQueryRewrite` is shared between
  `CREATE RULE` and `commands/view.c:DefineView`. [verified-by-code]
  `rewriteDefine.c:224`.
- INV-rls-1: **Default-deny.** RLS enabled with zero matching policies →
  the OR-of-PERMISSIVE collapses to `false`. [from-comment]
  `rowsecurity.c:7-10`.
- INV-rls-2: **PERMISSIVE composes with OR, RESTRICTIVE with AND.** Final
  shape: `(perm1 OR perm2 OR …) AND restr1 AND restr2 AND …`. RLS quals
  are prepended to whatever security quals already exist on the RTE (e.g.
  view-update permissions). [from-comment] `rowsecurity.c:1-21`.
- INV-rls-3: **WITH CHECK runs AFTER BEFORE INSERT/UPDATE triggers.** A
  trigger that mutates the new row may flip whether the policy admits it.
  [from-comment] `rowsecurity.c`.

## 6. Entry points (how the rest of the backend calls in)

Parser entry points used outside `parser/`:

- `raw_parser(text, mode)` — called by `tcop/postgres.c:pg_parse_query()`
  and PL/pgSQL.
- `pg_analyze_and_rewrite_fixedparams(...)`, `pg_analyze_and_rewrite_varparams(...)`,
  `pg_analyze_and_rewrite_withcb(...)` (in `tcop/postgres.c`) — convenience
  wrappers that call `parse_analyze_*` followed by `pg_rewrite_query()`.
  These are what tcop and the plancache actually use.
- `parse_sub_analyze(stmt, parent_pstate, ...)` — called by `parse_cte.c`
  (CTE bodies), `parse_clause.c` (sub-selects in FROM), `parse_expr.c`
  (SubLink subqueries), and rule-action processing in `rewriteHandler.c`.
- `transformExpr(pstate, expr, exprKind)` — exported to PL/pgSQL via the
  hook surface in `ParseState`.
- `addRangeTableEntry*` family — `parse_clause.c` is the main caller, but
  `commands/copy*.c`, `commands/explain*.c`, and `executor/spi.c` all
  manufacture transient RTEs through these helpers.
- `assign_query_collations(pstate, query)` — called from each
  `transformFooStmt` in `analyze.c`.

Rewriter entry points used outside `rewrite/`:

- `QueryRewrite(parsetree)` — exposed via
  `tcop/postgres.c:pg_rewrite_query()` (and via `parser/analyze.c`'s
  callers indirectly through the `analyze_and_rewrite_*` wrappers).
- `AcquireRewriteLocks(query, forExecute, forUpdatePushedDown)` — called
  by plancache, parallel-worker query deserialization, and the rule-loader
  path.
- `RewriteQuery(parsetree, rewrite_events, orig_rt_length)` — only called
  by `QueryRewrite` and recursively by itself.
- `fireRIRrules(parsetree, activeRIRs)` — internal but visible: also called
  recursively to process sublinks and CTE bodies.
- `get_row_security_policies(...)` — called only from `fireRIRrules`.
- `DefineQueryRewrite` — called by `CREATE RULE` (`utility.c`) and by
  `DefineView` (`commands/view.c`).

## 7. What the tests tell us

### Regression (`src/test/regress/sql/`)

- `rules.sql` — the rule-engine workhorse. Covers DO INSTEAD vs DO ALSO,
  conditional rules, rule-vs-trigger interaction, rule names, the
  `_RETURN` view machinery. The single best place to see the rewriter's
  observable contract.
- `rowsecurity.sql` — PERMISSIVE / RESTRICTIVE composition, BYPASSRLS,
  RLS + views, RLS + INSERT WITH CHECK, the trigger-mutation interaction.
- `with.sql` / `with_pg.sql` — WITH RECURSIVE, MATERIALIZED hint,
  data-modifying CTEs, SEARCH and CYCLE clauses (exercise
  `rewriteSearchCycle.c`).
- `merge.sql` — MERGE statement parse analysis, three-way WHEN matching,
  MERGE on partitioned tables, MERGE on updatable views (PG 17).
- `create_view.sql` — automatically-updatable views (which the rewriter
  implements by composing the `_RETURN` rule's targetlist with the
  UPDATE/DELETE/INSERT command).
- `subselect.sql`, `join.sql`, `groupingsets.sql`, `window.sql` — exercise
  the corresponding `parse_clause.c` / `parse_agg.c` transformers.
- `aggregates.sql` — `parseCheckAggregates` corner cases.

### Isolation (`src/test/isolation/`)

Rewriter behavior under concurrent schema change isn't isolation-tested
directly — the lock re-acquisition contract is exercised indirectly via
the plancache tests (`alter-table-1`, etc.).

### TAP

`src/test/recovery/` and `src/test/subscription/` exercise the rewriter
implicitly via DML on subscriber-side replicas; nothing parser-specific.

## 8. Gotchas / sharp edges

- **`p_expr_kind` is the feature-gate vocabulary.** When you add a new
  expression form, the failure mode "this works in SELECT target but
  ereports in WHERE" is almost always missing an `ExprKind` case in
  `parse_expr.c:transformXXX` or in `parse_agg.c:check_agglevels_and_constraints`.
- **`make_parsestate(NULL)` vs `make_parsestate(parent)`.** Sub-statements
  *must* be allocated with the parent, otherwise `Var.varlevelsup` won't
  reflect the nesting depth and the planner will produce wrong results
  for correlated subqueries.
- **`free_parsestate` releases `p_target_relation`.** Forgetting to call
  it on the error path leaks a relcache pin.
- **`resjunk` is a planner contract.** Items with `resjunk=true` are
  dropped by the executor's final projection but kept by the planner
  because legitimate sort keys live there. Forget the flag and you
  produce them in the output. [via
  `knowledge/files/src/backend/parser/parse_target.c.md`]
- **Locks at RTE-creation must match `rellockmode` exactly.** The
  rewriter's `AcquireRewriteLocks` reads the field directly; mismatches
  produce subtle deadlock-avoidance regressions because the lock
  manager's local hashtable distinguishes by mode.
- **The lookahead filter `base_yylex` is not optional.** Doing the
  lookahead inside flex would reintroduce backtracking; doing it inside
  bison would duplicate ambiguous productions. The filter is the third
  option. [verified-by-code] `parser.c:90-108`.
- **`Transform_null_equals` GUC.** When on, `expr = NULL` is rewritten to
  `expr IS NULL`. Backward-compat knob; off by default; expressly NOT
  applied to PL/pgSQL `=` in IF tests (those are normal SQL semantics).
- **`OprCache` and `func_get_detail` are syscache-invalidated.** The
  `InvalidateOprCacheCallBack` callback wires it up — extension code that
  manufactures functions/operators on the fly without `CacheInvalidate*`
  will see stale resolutions across DDL.
- **`UPDATE t SET (c1, c2) = (subquery)`** is the `MultiAssignRef` /
  `transformMultiAssignRef` path in `parse_expr.c` — a single
  per-`TargetEntry` walk is wrong; the helper threads the same subquery
  across all target entries it supplies.
- **The `EXCLUDED` pseudo-rel of ON CONFLICT** must remain `RTE_RELATION`
  even if the target relation is a view; `fireRIRrules` checks for it
  explicitly. Rewriting it as a subquery breaks
  `transformOnConflictArbiter`.
- **`rewriteTargetListIU` fills missing INSERT columns with defaults / nulls.**
  The parser only builds what the SQL text spelled. If you add a new
  default-source (generated columns, identity, OVERRIDING SYSTEM/USER VALUE)
  this is where the runtime side goes. [via
  `knowledge/files/src/backend/rewrite/rewriteHandler.c.md`]
- **`AcquireRewriteLocks` patches join-RTE Vars referring to dropped
  columns to null pointers** — necessary because stored rules can outlive
  the columns they reference. A walker that doesn't tolerate
  `Var=NULL` will crash post-`ALTER TABLE DROP COLUMN`.
- **Rules referencing ENRs (transition tables) are rejected at definition
  time** by `DefineQueryRewrite`. The diagnostic is intentional; transition
  tables are per-firing and can't be referenced by stored definitions.
- **`gram.y` is hand-written and large** (~524 KB). The bison `%prec` and
  `%nonassoc` directives encoding SQL's precedence are not commented —
  most edits touch one production and inadvertently change conflict counts
  elsewhere. `make` will report any new conflicts; never silence them.

## 9. Open questions

- O1: **RLS + user-defined INSTEAD rules.** When both a user-defined
  INSTEAD rule and an RLS policy exist on the same table, the rule is
  applied during `RewriteQuery` and produces a product query referencing
  the target table; the table's RLS policies are then added during
  `fireRIRrules` on the product query. Need case analysis to confirm
  this composes correctly when the rule action *also* references the
  source table. [unverified] (raised in
  `knowledge/files/src/backend/rewrite/rewriteHandler.c.md`)
- O2: **`stmt_requires_parse_analysis` vs `analyze_requires_snapshot`.** The
  comments at `analyze.c:512-529` say they're "same conditions, different
  reasons" — should they be a single predicate with two name aliases, or
  is there a planned future divergence (e.g., a statement that needs
  re-analysis but not a snapshot)? Reading the call sites in `tcop/` and
  `commands/` may settle this. [unverified]
- O3: **`PERMISSIVE` policy with `qual = NULL`.** The composition is
  `OR`-of-quals — what does a NIL qual contribute? Should be `TRUE`, but
  the code goes through `make_orclause` which collapses NIL lists; the
  failure mode is subtle. Spot-check `policyQuals_to_qual` (in
  `rowsecurity.c`) to confirm. [unverified]
- O4: **`MERGE` + view + RLS** (PG 17 updatable-views-via-MERGE). The
  interaction between view auto-rewrite, MERGE's three-way matching, and
  RLS post-pass ordering is new and only lightly tested by
  `src/test/regress/sql/merge.sql`. Could use a focused read of the
  PG-17 `transformMergeStmt` extensions plus the rewriter's MERGE path.
- O5: **`pg_stat_statements` and `JumbleQuery`.** Jumbling happens
  inside `parse_analyze_*` for queryId, but parameters' constants get
  normalized later in the jumble walker — the boundary between "jumble
  for cache key" and "jumble for normalization" is fuzzy. Worth chasing
  in `nodes/queryjumble.c` if `pg_stat_statements` semantics ever surprise.
- O6: **Cross-schema view recursion.** `activeRIRs` is a flat Oid list;
  it doesn't distinguish "view A includes view B includes view A" from
  legitimate self-reference patterns the planner has elsewhere. Likely
  fine (recursion at the SQL level is impossible without
  `WITH RECURSIVE`), but worth re-checking.

## 10. Related subsystems

- **Calls into:**
  - `utils/cache/syscache` + `utils/cache/relcache` — every catalog lookup
    in `parse_relation.c` / `parse_type.c` / `parse_func.c` /
    `parse_oper.c` / `parse_coerce.c`.
    [via `knowledge/subsystems/utils-cache.md`]
  - `storage/lmgr` — locks taken in `parse_relation.c:addRangeTableEntry`
    and re-acquired in `rewriteHandler.c:AcquireRewriteLocks`.
    [via `knowledge/subsystems/storage-lmgr.md`,
    `knowledge/idioms/locking-overview.md`]
  - `utils/mmgr` — every parser intermediate is allocated in the current
    `MessageContext` (per-message) or `PortalHeapMemory` (per-portal); the
    final `Query` tree is `copyObject`-able into a longer-lived context
    for plancache storage. [via `knowledge/subsystems/utils-mmgr.md`,
    `knowledge/idioms/memory-contexts.md`]
  - `commands/view.c` — `DefineView` calls `DefineQueryRewrite` to
    install the `_RETURN` rule.
  - `nodes/queryjumble.c` — `JumbleQuery` runs inside
    `parse_analyze_*` when `IsQueryIdEnabled()`.
  - `nodes/copyfuncs.c` / `nodes/equalfuncs.c` / `nodes/outfuncs.c` /
    `nodes/readfuncs.c` — generated from `parsenodes.h` via
    `gen_node_support.pl`. Adding a parsenode requires running the
    generator. [via `knowledge/idioms/node-types-and-lists.md`]

- **Called by:**
  - `tcop/postgres.c` — `exec_simple_query`, `exec_parse_message`,
    `exec_bind_message` all run `pg_parse_query` → `pg_analyze_and_rewrite_*`.
    [via `knowledge/files/src/backend/tcop/postgres.c.md`]
  - `utils/cache/plancache` — re-runs analysis + rewrite on cached plans
    when catalog versions invalidate (calls `AcquireRewriteLocks` on
    stored rule actions, full `pg_analyze_and_rewrite_*` on cached source).
  - `commands/prepare.c` — `PREPARE foo AS ...` runs the full pipeline.
  - `executor/spi.c` — `SPI_prepare`, `SPI_execute` paths.
  - PL/pgSQL (`src/pl/plpgsql/src/pl_handler.c`) — uses
    `raw_parser(..., RAW_PARSE_PLPGSQL_EXPR/STMT/...)` + the `ParseState`
    hook surface to plug its own variable resolution.

- **Sibling:**
  - `executor/` (planner output is what the executor runs) — see
    `knowledge/subsystems/executor.md`.
  - `optimizer/` (the planner sits between rewriter and executor) — see
    `knowledge/subsystems/optimizer.md`. The rewriter's output is the
    planner's input.

## 11. Source pointers — most-cited file:line summary

| Anchor | What it establishes |
|---|---|
| `parser/README:5-31` | The layered design + per-file roles |
| `parser/parser.c:42` | `raw_parser` entry |
| `parser/parser.c:111` | `base_yylex` lookahead filter |
| `parser/scan.l:9-22` | No-backtrack invariant + sync-with-frontend rule |
| `parser/gram.y:23-25` | "No catalog access in the grammar" |
| `parser/analyze.c:127,167,208` | Three `parse_analyze_*` entry points |
| `parser/analyze.c:271` | `transformTopLevelStmt` |
| `parser/analyze.c:334-444` | The dispatcher |
| `parser/analyze.c:363-367` | Three-sites-change caution |
| `parser/analyze.c:469-529` | `stmt_requires_parse_analysis` + `analyze_requires_snapshot` |
| `parser/parse_node.h:91-` | `ParseState` |
| `parser/parse_collate.c:5-12` | Why collation is a separate pass |
| `parser/parse_utilcmd.c:6-12` | Why DDL is deferred to ProcessUtility time |
| `nodes/parsenodes.h:117` | `Query` |
| `nodes/parsenodes.h:1137` | `RangeTblEntry` |
| `nodes/parsenodes.h:2187` | `RawStmt` |
| `rewrite/rewriteHandler.c:103-146` | Why `AcquireRewriteLocks` exists |
| `rewrite/rewriteHandler.c:148` | `AcquireRewriteLocks` entry |
| `rewrite/rewriteHandler.c:823` | `rewriteTargetListIU` — DML targetlist fill-in |
| `rewrite/rewriteHandler.c:1687` | `matchLocks` — rule lookup |
| `rewrite/rewriteHandler.c:2042` | `fireRIRrules` |
| `rewrite/rewriteHandler.c:2049-2063` | SEARCH/CYCLE hookup |
| `rewrite/rewriteHandler.c:2117-2138` | Materialized-views + `EXCLUDED` not view-expanded |
| `rewrite/rewriteHandler.c:2249-2255` | RLS-applied-last comment |
| `rewrite/rewriteHandler.c:2484` | `fireRules` — DO INSTEAD / conditional / DO ALSO partition |
| `rewrite/rewriteHandler.c:4044` | `RewriteQuery` |
| `rewrite/rewriteHandler.c:4055-4066` | WITH-clause rewritten first |
| `rewrite/rewriteHandler.c:4147-4149` | SELECTs not rewritten in `RewriteQuery` |
| `rewrite/rewriteHandler.c:4533` | RETURNING only in unconditional INSTEAD |
| `rewrite/rewriteHandler.c:4781-4870` | `QueryRewrite` + canSetTag fix |
| `rewrite/rewriteDefine.c:52` | `InsertRule` — `pg_rewrite` insert + dep registration |
| `rewrite/rewriteDefine.c:190,224` | `DefineRule` / `DefineQueryRewrite` |
| `rewrite/rowsecurity.c:1-21` | RLS scope + composition rules |
| `rewrite/rowsecurity.c:7-10` | Default-deny |

## Synthesized over

This synthesis distills the per-file corpus under
`knowledge/files/src/backend/parser/` and
`knowledge/files/src/backend/rewrite/` (33 docs in the two directories).
See [[knowledge/idioms/parser-pipeline.md]] for the end-to-end narrative
and [[knowledge/subsystems/optimizer.md]] for what consumes this stage's
output.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**65 files.**

| File |
|---|
| [`src/backend/parser/README`](../files/src/backend/parser/README.md) |
| [`src/backend/parser/analyze.c`](../files/src/backend/parser/analyze.c.md) |
| [`src/backend/parser/gram.y`](../files/src/backend/parser/gram.y.md) |
| [`src/backend/parser/gramparse.h`](../files/src/backend/parser/gramparse.h.md) |
| [`src/backend/parser/parse_agg.c`](../files/src/backend/parser/parse_agg.c.md) |
| [`src/backend/parser/parse_clause.c`](../files/src/backend/parser/parse_clause.c.md) |
| [`src/backend/parser/parse_coerce.c`](../files/src/backend/parser/parse_coerce.c.md) |
| [`src/backend/parser/parse_collate.c`](../files/src/backend/parser/parse_collate.c.md) |
| [`src/backend/parser/parse_cte.c`](../files/src/backend/parser/parse_cte.c.md) |
| [`src/backend/parser/parse_enr.c`](../files/src/backend/parser/parse_enr.c.md) |
| [`src/backend/parser/parse_expr.c`](../files/src/backend/parser/parse_expr.c.md) |
| [`src/backend/parser/parse_func.c`](../files/src/backend/parser/parse_func.c.md) |
| [`src/backend/parser/parse_graphtable.c`](../files/src/backend/parser/parse_graphtable.c.md) |
| [`src/backend/parser/parse_jsontable.c`](../files/src/backend/parser/parse_jsontable.c.md) |
| [`src/backend/parser/parse_merge.c`](../files/src/backend/parser/parse_merge.c.md) |
| [`src/backend/parser/parse_node.c`](../files/src/backend/parser/parse_node.c.md) |
| [`src/backend/parser/parse_oper.c`](../files/src/backend/parser/parse_oper.c.md) |
| [`src/backend/parser/parse_param.c`](../files/src/backend/parser/parse_param.c.md) |
| [`src/backend/parser/parse_relation.c`](../files/src/backend/parser/parse_relation.c.md) |
| [`src/backend/parser/parse_target.c`](../files/src/backend/parser/parse_target.c.md) |
| [`src/backend/parser/parse_type.c`](../files/src/backend/parser/parse_type.c.md) |
| [`src/backend/parser/parse_utilcmd.c`](../files/src/backend/parser/parse_utilcmd.c.md) |
| [`src/backend/parser/parser.c`](../files/src/backend/parser/parser.c.md) |
| [`src/backend/parser/scan.l`](../files/src/backend/parser/scan.l.md) |
| [`src/backend/parser/scansup.c`](../files/src/backend/parser/scansup.c.md) |
| [`src/backend/rewrite/rewriteDefine.c`](../files/src/backend/rewrite/rewriteDefine.c.md) |
| [`src/backend/rewrite/rewriteGraphTable.c`](../files/src/backend/rewrite/rewriteGraphTable.c.md) |
| [`src/backend/rewrite/rewriteHandler.c`](../files/src/backend/rewrite/rewriteHandler.c.md) |
| [`src/backend/rewrite/rewriteManip.c`](../files/src/backend/rewrite/rewriteManip.c.md) |
| [`src/backend/rewrite/rewriteRemove.c`](../files/src/backend/rewrite/rewriteRemove.c.md) |
| [`src/backend/rewrite/rewriteSearchCycle.c`](../files/src/backend/rewrite/rewriteSearchCycle.c.md) |
| [`src/backend/rewrite/rewriteSupport.c`](../files/src/backend/rewrite/rewriteSupport.c.md) |
| [`src/backend/rewrite/rowsecurity.c`](../files/src/backend/rewrite/rowsecurity.c.md) |
| [`src/include/parser/analyze.h`](../files/src/include/parser/analyze.h.md) |
| [`src/include/parser/kwlist.h`](../files/src/include/parser/kwlist.h.md) |
| [`src/include/parser/parse_agg.h`](../files/src/include/parser/parse_agg.h.md) |
| [`src/include/parser/parse_clause.h`](../files/src/include/parser/parse_clause.h.md) |
| [`src/include/parser/parse_coerce.h`](../files/src/include/parser/parse_coerce.h.md) |
| [`src/include/parser/parse_collate.h`](../files/src/include/parser/parse_collate.h.md) |
| [`src/include/parser/parse_cte.h`](../files/src/include/parser/parse_cte.h.md) |
| [`src/include/parser/parse_enr.h`](../files/src/include/parser/parse_enr.h.md) |
| [`src/include/parser/parse_expr.h`](../files/src/include/parser/parse_expr.h.md) |
| [`src/include/parser/parse_func.h`](../files/src/include/parser/parse_func.h.md) |
| [`src/include/parser/parse_graphtable.h`](../files/src/include/parser/parse_graphtable.h.md) |
| [`src/include/parser/parse_merge.h`](../files/src/include/parser/parse_merge.h.md) |
| [`src/include/parser/parse_node.h`](../files/src/include/parser/parse_node.h.md) |
| [`src/include/parser/parse_oper.h`](../files/src/include/parser/parse_oper.h.md) |
| [`src/include/parser/parse_param.h`](../files/src/include/parser/parse_param.h.md) |
| [`src/include/parser/parse_relation.h`](../files/src/include/parser/parse_relation.h.md) |
| [`src/include/parser/parse_target.h`](../files/src/include/parser/parse_target.h.md) |
| [`src/include/parser/parse_type.h`](../files/src/include/parser/parse_type.h.md) |
| [`src/include/parser/parse_utilcmd.h`](../files/src/include/parser/parse_utilcmd.h.md) |
| [`src/include/parser/parser.h`](../files/src/include/parser/parser.h.md) |
| [`src/include/parser/parsetree.h`](../files/src/include/parser/parsetree.h.md) |
| [`src/include/parser/scanner.h`](../files/src/include/parser/scanner.h.md) |
| [`src/include/parser/scansup.h`](../files/src/include/parser/scansup.h.md) |
| [`src/include/rewrite/prs2lock.h`](../files/src/include/rewrite/prs2lock.h.md) |
| [`src/include/rewrite/rewriteDefine.h`](../files/src/include/rewrite/rewriteDefine.h.md) |
| [`src/include/rewrite/rewriteGraphTable.h`](../files/src/include/rewrite/rewriteGraphTable.h.md) |
| [`src/include/rewrite/rewriteHandler.h`](../files/src/include/rewrite/rewriteHandler.h.md) |
| [`src/include/rewrite/rewriteManip.h`](../files/src/include/rewrite/rewriteManip.h.md) |
| [`src/include/rewrite/rewriteRemove.h`](../files/src/include/rewrite/rewriteRemove.h.md) |
| [`src/include/rewrite/rewriteSearchCycle.h`](../files/src/include/rewrite/rewriteSearchCycle.h.md) |
| [`src/include/rewrite/rewriteSupport.h`](../files/src/include/rewrite/rewriteSupport.h.md) |
| [`src/include/rewrite/rowsecurity.h`](../files/src/include/rewrite/rowsecurity.h.md) |

<!-- /files-owned:auto -->
