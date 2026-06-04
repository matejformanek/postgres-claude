# analyze.c

- **Source:** `source/src/backend/parser/analyze.c` (4103 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (entry points + dispatcher; per-kind transforms skim)

## Purpose

Top of parse analysis: transform a raw parse tree into a `Query` tree. For
optimizable statements (DML + SELECT) this includes lock acquisition, RTE
construction, expression typing, target-list build. For utility commands
(DDL) it wraps the raw tree unchanged in a `CMD_UTILITY` Query — those are
re-analyzed at execution time by `parse_utilcmd.c`. [from-comment] `:6-14`

## Entry points

| Line | Symbol | Used by |
|---|---|---|
| 126 | `parse_analyze_fixedparams` | tcop / SPI when `$n` types are known upfront |
| 166 | `parse_analyze_varparams` | `PREPARE` / extended protocol when types must be deduced |
| 207 | `parse_analyze_withcb` | callers (e.g. PL/pgSQL) supplying their own param resolver |
| 243 | `parse_sub_analyze` | recursion into sub-statements (CTE bodies, INSERT-from-SELECT, etc.) |
| 270 | `transformTopLevelStmt` | thin wrapper: stash `stmt_location` / `stmt_len` and dispatch |
| 334 | `transformStmt` | the dispatcher — switch on `nodeTag(parseTree)` |

All four public `parse_analyze_*` flavors do the same three things: build a
`ParseState`, call `transformTopLevelStmt`, then optionally jumble
(`JumbleQuery` for query-id when `IsQueryIdEnabled()`) and fire
`post_parse_analyze_hook`. [verified-by-code] `:146-150, :188-192, :225-229`

## The dispatcher

`transformStmt` `:334-444` switches on `nodeTag` and routes to one of:

| Node | Handler | What it builds |
|---|---|---|
| `T_InsertStmt`  | `transformInsertStmt`  | `Query{commandType=CMD_INSERT}` |
| `T_DeleteStmt`  | `transformDeleteStmt`  | `Query{commandType=CMD_DELETE}` |
| `T_UpdateStmt`  | `transformUpdateStmt`  | `Query{commandType=CMD_UPDATE}` |
| `T_MergeStmt`   | `transformMergeStmt` (in `parse_merge.c`) | `Query{commandType=CMD_MERGE}` |
| `T_SelectStmt`  | three sub-paths: VALUES → `transformValuesClause`, `op==SETOP_NONE` → `transformSelectStmt`, else `transformSetOperationStmt` | `Query{commandType=CMD_SELECT}` |
| `T_ReturnStmt` / `T_PLAssignStmt` | PL/pgSQL fast-paths | `Query{commandType=CMD_SELECT}` |
| `T_DeclareCursorStmt` / `T_ExplainStmt` / `T_CreateTableAsStmt` / `T_CallStmt` | each has a dedicated transformer because they *wrap* an optimizable stmt | mixed |
| default | utility shortcut: wrap raw stmt in `Query{commandType=CMD_UTILITY, utilityStmt=parseTree}` | utility |

[verified-by-code] `:368-444`. Caution comment at `:363-367` mandates that
any change here must also update `stmt_requires_parse_analysis()` and
`analyze_requires_snapshot()`.

## Companion predicates

- `stmt_requires_parse_analysis(RawStmt *)` `:468-505` — true when
  `transformStmt` does more than the utility wrap. Used by tcop/plancache to
  decide whether re-analysis is needed.
- `analyze_requires_snapshot(RawStmt *)` `:512-529` — currently delegates to
  the above; documented as "same conditions, different reason" so callers
  read better.
- `query_requires_rewrite_plan(Query *)` `:541-…` — one step further down:
  is rewriting/planning non-trivial for this already-analyzed Query?

## SELECT-INTO trick

`transformOptionalSelectInto` `:294-327` runs *before* `transformStmt` and
rewrites a top-level `SELECT ... INTO t` into a `CreateTableAsStmt`. Only
the top-level call (`transformTopLevelStmt`) takes this path; recursive
`parse_sub_analyze` does not, because a `SELECT INTO` is illegal as a
sub-statement.

## Hooks

- `post_parse_analyze_hook` `:74` — extension hook fired once per analyzed
  query, with the jumble state if computed. `pg_stat_statements` uses it to
  collect query-id + the source text.

## Per-statement transformers (not deep-read in this pass)

Each lives further down in the file:

- `transformInsertStmt` — builds RTE for target rel, processes column list,
  `VALUES`/SELECT source, `ON CONFLICT`, `RETURNING`.
- `transformDeleteStmt` / `transformUpdateStmt` — target-rel RTE +
  `USING`/`FROM` aliases, target-list (UPDATE) and WHERE, RETURNING.
- `transformSelectStmt` — the big one: FROM (`transformFromClause`), WHERE,
  GROUP/HAVING/WINDOW, target list, DISTINCT, ORDER/LIMIT/FETCH,
  locking clauses, WITH.
- `transformSetOperationStmt` / `transformSetOperationTree` — UNION /
  INTERSECT / EXCEPT trees with type unification across arms.
- `transformValuesClause` — standalone `VALUES ( ), ( )` SELECT-of-a-VALUES.

## What this file does NOT do

- It does not run the lexer/grammar (that's `parser.c`).
- It does not resolve operators / functions / coercions on its own — those
  delegate to `parse_oper.c` / `parse_func.c` / `parse_coerce.c` via the
  helpers in `parse_expr.c`.
- It does not handle utility-stmt parse analysis. Even though the wrap
  happens here, the *work* is `parse_utilcmd.c` at execution time.

## Caveats

- After a refactor adds a new optimizable statement type, three sites must
  change together: the switch in `transformStmt`, the lists in
  `stmt_requires_parse_analysis` and `analyze_requires_snapshot`. The
  `Caution` comment `:363-367` is load-bearing.
- `analyze_requires_snapshot` is *not* a free function: callers must take
  the snapshot before calling `parse_analyze_*` if it returns true.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/parser-pipeline.md](../../../../idioms/parser-pipeline.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
