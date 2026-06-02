# 2026-06-02 — parser + rewrite spine synthesis

**Type:** interactive (worktree `ft_corpus_parser_rewrite`).
**Outcome:** `knowledge/subsystems/parser-and-rewrite.md`, 766 lines, 47
confidence-tagged cites, verified against source commit `4b0bf0788b0`.

## What this session did

Closed a long-standing gap: parser/ + rewrite/ had 33 per-file docs and a
nicely curated `knowledge/idioms/parser-pipeline.md`, but no
directory-level synthesis. After the §5.3 priority ordering in
`pg-claude-plan.md` and the post-compact handoff conversation, this was
the highest-value next pick (priority 9 in the plan).

The synthesis covers:

1. The **two-stage / four-pass pipeline** (raw parse → parse-analyze →
   rewrite → planner handoff), with the file-level division of labor
   inside each stage.
2. **Seven key data structures** beyond what the idiom doc already
   documents: `RawStmt` (raw root), `Query` (the analyzed contract with
   the rest of the backend), `RangeTblEntry` (the discriminated union of
   RTE kinds), `ParseState` (the parser's scratchpad with hook surface),
   `RewriteRule` (in-memory `pg_rewrite` row), `CommonTableExpr`,
   `TargetEntry`.
3. **18 invariants**, tagged INV-parser-* / INV-rewrite-* / INV-rls-*.
   Most load-bearing:
   - INV-rewrite-3: **RLS is applied LAST inside `fireRIRrules`** — the
     reason is sublink-double-recursion avoidance, and the ordering
     comment at `rewriteHandler.c:2249-2255` is the single sentence that
     makes the whole rewriter understandable.
   - INV-parser-6: **The three-sites-change rule** — adding a new
     optimizable-statement node type requires changes to the switch in
     `transformStmt`, the list in `stmt_requires_parse_analysis()`,
     and the list in `analyze_requires_snapshot()`. Skipping one leaves
     plancache silently wrong.
   - INV-rewrite-5: **`AcquireRewriteLocks` is the FIRST step for any
     non-fresh Query** (rule body loaded from `pg_rewrite.ev_action`,
     view body, plancache entry).
   - INV-rls-1: **Default-deny** — RLS enabled with zero matching
     policies collapses to `false`.
4. **Entry points** the rest of the backend calls (with concrete callers
   in tcop / plancache / SPI / PL/pgSQL).
5. **Gotchas** distilled from the per-file docs (`p_expr_kind` is the
   feature-gate vocabulary; `make_parsestate(NULL)` vs
   `make_parsestate(parent)`; `free_parsestate` releases the held
   relation; `resjunk` is a planner contract; the `EXCLUDED` pseudo-rel
   must not be view-expanded).
6. **Most-cited file:line table** in §11 — a quick-glance index of the
   top anchors anyone reading the doc will want to jump to.
7. **Open questions** §9 — six items, mostly composability questions
   between PG17/18 features (MERGE-on-views + RLS; cross-schema view
   recursion; `pg_stat_statements` jumble boundary).

## What I did NOT do

- **Did not re-read all 33 per-file docs.** Pulled the spine: README,
  `parser.c`, `analyze.c`, `parse_node.c`, `parse_clause.c`,
  `parse_expr.c`, `parse_relation.c`, `parse_target.c`, `parse_func.c`,
  `parse_oper.c`, `parse_coerce.c`, `parse_collate.c`, `parse_agg.c`,
  `parse_cte.c`, `parse_merge.c`, `parse_param.c`, `parse_utilcmd.c`,
  `gram.y`, `scan.l`, plus all 8 rewrite/ docs (`rewriteHandler.c`,
  `rewriteDefine.c`, `rewriteManip.c`, `rewriteSearchCycle.c`,
  `rowsecurity.c`, etc.). The remaining ~15 per-file docs (mostly
  headers + small parser leaves) are background.
- **Did not register new rows in `files-examined.md`.** All the source
  files cited are already in the registry from the original per-file
  passes (this synthesis re-uses their depth-readings).
- **Did not run the dev cluster.** This is a synthesis pass; no code
  edits, no tests run.

## Verification

- Verified all called-out line numbers (`raw_parser:42`, `base_yylex:111`,
  `parse_analyze_fixedparams:127`, `parse_analyze_varparams:167`,
  `parse_analyze_withcb:208`, `parse_sub_analyze:244`,
  `transformTopLevelStmt:271`, `transformStmt:334`,
  `stmt_requires_parse_analysis:469`, `analyze_requires_snapshot:513`,
  `AcquireRewriteLocks:148`, `rewriteTargetListIU:823`, `matchLocks:1687`,
  `fireRIRrules:2042`, `fireRules:2484`, `RewriteQuery:4044`,
  `QueryRewrite:4781`) via `grep -n` against the live source at commit
  `4b0bf0788b0`.
- Verified `parsenodes.h` anchors: `Query` at `:117`, `RangeTblEntry` at
  `:1137`, `RawStmt` at `:2187`, `QuerySource` enum at `:34`.

## Tagging conventions used

- `[verified-by-code]` — claim cross-checked against a specific
  `file:line` in this session.
- `[from-README]` — sourced from `parser/README`.
- `[from-comment]` — sourced from an in-file comment block at the cited
  line range.
- `[unverified]` — open questions or cross-feature composition claims
  not directly checked; marked in §9 Open Questions.

## Ledger updates

- `progress/coverage.md` — appended `parser-and-rewrite` row.
- `progress/STATE.md` — bumped subsystem count 16→17 + 20→21
  (subsystem+data-structures), updated Phase + Last-activity, added this
  session log to Recent.
- `progress/files-examined.md` — no new rows (all files already
  registered from the original per-file passes).

## Followup candidates (not done this session)

- §9 Open Question O1: RLS + user-defined INSTEAD rules — case-analysis
  the composability claim by reading `fireRIRrules` against the
  rule-substitution path step-by-step with a worked example.
- §9 Open Question O3: `policyQuals_to_qual` with NIL — spot-check
  `make_orclause` behavior on NIL inputs.
- §9 Open Question O4: MERGE + view + RLS — PG17 added updatable views
  via MERGE; the rewriter's special handling deserves a focused read.
- Stretch: add a `knowledge/data-structures/parsestate-hooks.md` zooming
  in on the `p_paramref_hook` / `p_pre_columnref_hook` / `p_post_columnref_hook`
  / `p_coerce_param_hook` surface — it's the API PL/pgSQL uses but it's
  scattered across `parse_node.h`, `parse_param.c`, and `parse_expr.c`.

## Why this matters

The parser+rewrite directories are the **second-largest source of
confident-but-wrong claims** about PG (after locking). Concrete examples
of mistakes this synthesis is structured to catch:

- Claiming the rewriter runs before parse-analyze (it doesn't).
- Claiming DDL is parse-analyzed at parse time (it isn't —
  `parse_utilcmd.c` runs at `ProcessUtility` time).
- Claiming RLS is applied during view expansion (it's applied after, by
  design).
- Claiming `Var.varlevelsup` is set by the planner (it's set by
  `parse_node.c:make_var` at parse-analyze time, using the
  `p_parent_parsestate` chain).
- Claiming every view rule is conditional (every view is an
  *unconditional* INSTEAD `_RETURN` rule).

Citing the file:line for each load-bearing claim is the Multigres lesson
applied to the area where it bites hardest.
