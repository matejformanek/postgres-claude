# parse_node.h

- **Source:** `source/src/include/parser/parse_node.h` (~410 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Defines the parser's three central in-memory state types: `ParseState`,
`ParseNamespaceItem`, `ParseNamespaceColumn`. Plus the `ParseExprKind`
enum and the parser-hook function signatures.

## ParseExprKind `:38-87`

44-value enum tagging the surrounding context of a `transformExpr` call.
Used by all `parse_*` files for context-specific error messages and feature
gating. Selection of common values:

- `EXPR_KIND_SELECT_TARGET` / `EXPR_KIND_INSERT_TARGET` /
  `EXPR_KIND_UPDATE_SOURCE` / `EXPR_KIND_UPDATE_TARGET` — DML positions.
- `EXPR_KIND_WHERE` / `EXPR_KIND_HAVING` / `EXPR_KIND_JOIN_ON` — quals.
- `EXPR_KIND_GROUP_BY` / `EXPR_KIND_ORDER_BY` / `EXPR_KIND_DISTINCT_ON`.
- `EXPR_KIND_LIMIT` / `EXPR_KIND_OFFSET` (Var-free enforced).
- Window-related: `EXPR_KIND_WINDOW_PARTITION`, `_ORDER`, `_FRAME_RANGE`,
  `_FRAME_ROWS`, `_FRAME_GROUPS`.
- DDL contexts: `EXPR_KIND_CHECK_CONSTRAINT`, `_DOMAIN_CHECK`,
  `_COLUMN_DEFAULT`, `_FUNCTION_DEFAULT`, `_INDEX_EXPRESSION`,
  `_INDEX_PREDICATE`, `_STATS_EXPRESSION`, `_GENERATED_COLUMN`.
- Extension-reserved: `EXPR_KIND_OTHER` — no enforcement applied; caller
  must police.

## Parser hooks `:93-98`

```c
typedef Node *(*PreParseColumnRefHook) (ParseState *, ColumnRef *);
typedef Node *(*PostParseColumnRefHook)(ParseState *, ColumnRef *, Node *);
typedef Node *(*ParseParamRefHook)     (ParseState *, ParamRef *);
typedef Node *(*CoerceParamHook)       (ParseState *, Param *, Oid, int32, int);
```

Wired into `pstate->p_*_hook`, used by PL/pgSQL and `parse_param.c` to
hijack column / $n resolution.

## ParseState struct `:211-263`

The scratchpad threaded through every parser helper. Critical fields:

| Field | Role |
|---|---|
| `parentParseState` | outer-query pstate for sub-queries (drives `Var.varlevelsup`) |
| `p_sourcetext` | for `ERRPOSITION` cursor in error messages |
| `p_rtable` / `p_rteperminfos` | growing range-table + per-RTE permissions |
| `p_joinexprs` | one-for-one with `p_rtable`, holds the JoinExpr for `RTE_JOIN` entries |
| `p_nullingrels` | per-RTE Bitmapset of outer-join indexes that can null it |
| `p_joinlist` | becomes `FromExpr.fromlist` in the finished Query |
| `p_namespace` | currently visible RTEs (a subset of `p_rtable`) — see `ParseNamespaceItem` |
| `p_lateral_active` | true while parsing a LATERAL subexpression |
| `p_ctenamespace` / `p_future_ctes` | visible WITH items / scoped-out ones (for hints) |
| `p_target_relation` / `p_target_nsitem` | INSERT/UPDATE/DELETE/MERGE target |
| `p_windowdefs` | accumulator for WINDOW / OVER; indexed by winref |
| `p_expr_kind` | current `ParseExprKind` |
| `p_next_resno` | next `TargetEntry.resno` to assign |
| `p_multiassign_exprs` | for `(a,b) = (subselect)` |
| `p_locking_clause` / `p_locked_from_parent` | FOR UPDATE/SHARE state |
| `p_resolve_unknowns` | true → resolve UNKNOWN-typed SELECT outputs as TEXT |
| `p_queryEnv` | ephemeral named relations / cursor enumeration |
| `p_graph_table_pstate` | scratch state for current GRAPH_TABLE |
| `p_hasAggs` / `p_hasWindowFuncs` / `p_hasTargetSRFs` / `p_hasSubLinks` / `p_hasModifyingCTE` | feature bits flipped during transforms, eventually copied to `Query` |
| `p_last_srf` | recent set-returning func/op, for nested-SRF error detection |
| `p_*_hook` + `p_ref_hook_state` | extension hooks |

## ParseNamespaceItem `:312-325`

Per-visible-RTE record. Two key boolean pairs:

- `p_rel_visible` (qualified-ref OK) vs. `p_cols_visible` (unqualified OK)
  — they differ for JOIN-without-alias and subquery-without-alias.
- `p_lateral_only` (visible only inside LATERAL) + `p_lateral_ok`
  (whether using it is legal at all — UPDATE/DELETE target rejects).

`p_returning_type` carries OLD/NEW marker for RETURNING. `p_perminfo`
links to `RTEPermissionInfo` for column-level privilege accounting.

## ParseNamespaceColumn `:348-359`

One per column of an `nsitem`. Carries both the *semantic* referent
(`p_varno`/`p_varattno` — what the runtime Var must point at) and the
*syntactic* referent (`p_varnosyn`/`p_varattnosyn` — what ruleutils.c uses
when round-tripping back to SQL text). They diverge when a JOIN alias
hides the underlying RTE's name.

Dropped columns: all-zero struct, conventionally `p_varno == 0` test.

## Exported entry points `:370-`

`make_parsestate`, `free_parsestate`, `parser_errposition`,
`transformContainerType`, `transformContainerSubscripts`, `make_var`,
`make_const`, `make_andclause`, and the `parser_errposition_callback`
plumbing.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
