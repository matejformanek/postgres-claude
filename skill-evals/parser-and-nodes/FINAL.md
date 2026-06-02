# parser-and-nodes — final eval report

## Summary

| Iteration | with_skill | baseline | delta (with - base) |
| --- | --- | --- | --- |
| 1 | 27 / 27 (100%) | 13 / 27 (48.1%) | +14 |
| 2 | 27 / 27 (100%) | 13 / 27 (48.1%) | +14 |

The skill is at ceiling on the assertion list across both iterations. Iter-2 did not change the *score*; it changed *where the content lives*.

## What changed in iter-2

Three edits applied to `.claude/skills/parser-and-nodes/SKILL.md`:

1. **Edit 1 — nodeFuncs.c maintenance points inlined**: the giant-switch list (`exprType`, `exprTypmod`, `exprCollation`, `exprSetCollation`, `exprInputCollation`, `exprLocation`, `expression_tree_walker_impl`, `expression_tree_mutator_impl`, `raw_expression_tree_walker_impl`, `set_opfuncid`) now lives inline in §"new Node" step 5, with verified line cites (`:42`, `:304`, `:826`, `:1092`, `:1140`, `:1403`, `:1890`, `:2111`, `:3018`, `:4115`). Previously this content was only in the `nodeFuncs.c` file-doc, requiring a round-trip read.

2. **Edit 2 — analyze.c three-site Caution inlined**: the `transformStmt` / `stmt_requires_parse_analysis` / `analyze_requires_snapshot` triple-update rule (analyze.c:363-367 / :469-505 / :513-529) is now in §"new SQL statement" step 4. This is a load-bearing trap (silent plancache miscompare) and deserves first-class placement.

3. **Edit 3 — new §"Tools for working with an existing tree"**: explicit pointers to `copyObject` / `equal` / `nodeToString` / `stringToNode` / `expression_tree_walker` / `_mutator` / `query_tree_walker` / `planstate_tree_walker` with the relevant line cites (`nodes.h:228-233`, `copyfuncs.c:177-212`, `copyfuncs.c:185`, `nodeFuncs.h:22-34`, `nodeFuncs.h:155-183`) and the mutator/walker contracts. Previously the SKILL talked about *generating* copy/equal funcs but never about *using* them — eval 2 is the canonical "I have a Node *, how do I copy it?" case.

Edit 4 (companion-doc cross-linking) was a no-op per the proposal.

## Line-number corrections vs proposal

The proposed edits had several off-by-one or off-by-few line cites. Verified against current `source/src/...` and applied with corrections (logged in `iteration-2/edits-applied.md`). The substantive ones:

- transformStmt body: `:334-444` → `:334-451` (the function actually ends at 451).
- `stmt_requires_parse_analysis`: `:468-505` → `:469-505`.
- `analyze_requires_snapshot`: `:512-529` → `:513-529`.
- `copyObjectImpl`: `:176-212` → `:177-212`.
- `QTW_*` flags: `:21-34` → `:22-34`.

The collation triplet (`exprCollation`/`exprSetCollation`/`exprInputCollation`) was split into three explicit cites (`:826`, `:1140`, `:1092`) rather than the proposal's single `:826+` blob, and the walker/mutator/`set_opfuncid` functions gained explicit cites (`:2111`, `:3018`, `:4115`, `:1890`).

## Why score didn't move

Iter-1 was already at 27/27. The iter-2 edits are a structural improvement (content moved from the file-doc into the SKILL itself, reducing the file-read round-trip the iter-1 with_skill answers had to take) but don't surface any new assertion. The baseline answers were generated from general PG knowledge without consulting the skill, so they are by construction unchanged across iterations.

If we wanted to drive the *baseline* score down (i.e. widen the skill's marginal advantage), we'd add harder assertions — e.g. "names the specific GUC `debug_raw_expression_coverage_test`", "cites `pg_rewrite.ev_action` as the storage site that forces catversion bumps", "knows the macro wrappers are in `nodeFuncs.h` not `nodeFuncs.c`". These are all things only the skill teaches; the baseline misses them in iter-1 already, so adding them would have widened the gap but the existing list doesn't.

## Recommendation

Skill is in good shape. **No iter-3 needed** unless the assertion list is sharpened. Closing the file-doc round-trip (iter-2's actual win) is invisible to the assertion grader but a real improvement for an interactive user — every nodeFuncs.c maintenance question and every analyze.c three-site caution is now answerable from SKILL.md without a second file read.
