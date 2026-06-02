# Proposed SKILL.md edits — parser-and-nodes, iteration 1

## Observed gaps

The skill is already strong and produced full-credit answers on all three evals. The findings below are mostly small additions that would close near-miss gaps where the baseline also got partial credit, and would make the skill self-sufficient (the with_skill answers had to lean on the file-doc for `nodeFuncs.c` to enumerate `exprType` / `exprTypmod` / `exprCollation` / `exprLocation` maintenance points — that list deserves to live in SKILL.md proper, since "I added an expression node, what else do I need to touch?" is one of the canonical questions).

## Proposed edits

### Edit 1 — make the "five maintenance points per expression node" explicit

**Rationale**: SKILL.md §"new Node" step 5 mentions adding walker cases generically. The actual rule from the README + `nodeFuncs.c` is that *every* expression node needs cases in five-to-eight switches. Calling out the list inline avoids a round-trip through the file-doc.

```json
{
  "old_string": "5. Add cases to `nodeFuncs.c` (`expression_tree_walker_impl`, `expression_tree_mutator_impl`, `raw_expression_tree_walker_impl`) if your node holds child expressions/plans that walkers must descend into. Grep for a sibling node type to find every place that needs touching.",
  "new_string": "5. If your node is an **expression** (lives in primnodes.h or has child Expr fields), add cases to **every** giant switch in `nodeFuncs.c`:\n   - `exprType` (`:42+`), `exprTypmod` (`:304+`), `exprCollation` / `exprSetCollation` / `exprInputCollation` (`:826+`), `exprLocation` (`:1403+`) — type/typmod/collation/location introspection.\n   - `expression_tree_walker_impl`, `expression_tree_mutator_impl` — recursion into children.\n   - `raw_expression_tree_walker_impl` — only if the node can appear in raw parsetrees.\n   - `set_opfuncid` family — only if your node holds an operator OID needing resolution.\n   Grep `T_<SiblingNode>` (e.g. `T_OpExpr`) to find every site; five-to-eight maintenance points per node, miss one and walkers silently misbehave."
}
```

### Edit 2 — surface the analyze.c three-site Caution

**Rationale**: with_skill answers cited this from the file-doc. It's a load-bearing trap (silent plancache miscompare) that belongs in the SKILL inline.

```json
{
  "old_string": "   - Optimizable statement → add a `transformFooStmt(ParseState *, FooStmt *)` in `parser/analyze.c` and wire it into the `switch (nodeTag(parseTree))` inside `transformStmt` (analyze.c:368).",
  "new_string": "   - Optimizable statement → add a `transformFooStmt(ParseState *, FooStmt *)` in `parser/analyze.c` and wire it into the `switch (nodeTag(parseTree))` inside `transformStmt` (analyze.c:334-444). **Caution (analyze.c:363-367)**: any change to that switch must also be reflected in `stmt_requires_parse_analysis()` (`:468-505`) and `analyze_requires_snapshot()` (`:512-529`) — three sites, one logical change."
}
```

### Edit 3 — explicit copy-tooling pointer

**Rationale**: "I have a Node *, how do I copy it?" came up in eval 2 and is one of the highest-traffic parser/nodes questions. SKILL.md doesn't currently name `copyObject` at all — it talks about the *generation* of copy funcs but not the *use* of them. A two-line pointer would make the skill self-contained for that question.

```json
{
  "old_string": "Companion docs: `knowledge/idioms/parser-pipeline.md`, `knowledge/idioms/node-types-and-lists.md`.",
  "new_string": "Companion docs: `knowledge/idioms/parser-pipeline.md`, `knowledge/idioms/node-types-and-lists.md`.\n\n## Tools for working with an existing tree\n\n- `copyObject(p)` — deep copy (preserves argument type via `typeof_unqual` macro, `nodes.h:228-233`). Dispatcher in `copyfuncs.c:176-212`, with `check_stack_depth()` guard. By-ref Datums go through `_copyConst` → `datumCopy`; `T_List` is deep-copied, `T_IntList`/`T_OidList`/`T_XidList` shallow.\n- `equal(a, b)` — deep structural compare (`equalfuncs.c`).\n- `nodeToString(p)` / `stringToNode(s)` — Lisp-ish text serialization; load-bearing for plan cache, rule storage (`pg_rewrite.ev_action`), parallel-worker plan shipping.\n- `expression_tree_walker` / `_mutator` — polymorphic recursion over expression trees (post-analysis). `raw_expression_tree_walker` for the pre-analysis shape (`A_Expr`, `ColumnRef`). `query_tree_walker` / `_mutator` wrap for Query, with `QTW_*` flags (`nodeFuncs.h:21-34`) to control rtable/CTE descent."
}
```

### Edit 4 — Note that `parser-pipeline.md` covers stage details and link more visibly

**Rationale**: Minor. Both companion docs are mentioned at the top but the SKILL body doesn't reference them again where most relevant. Skipping unless we want to over-engineer; flagged for future iteration.

(No diff proposed in this iteration.)
