# Adding `BLEND <target> INTO <source>`

`BLEND` is a brand-new top-level optimizable statement, so it touches grammar, kwlist, parsenodes.h, analyze.c, and the auto-generated copy/equal/out/read funcs. Walk the layers in this order so each build fails fast:

## 1. Keyword

- `src/include/parser/kwlist.h` — add `PG_KEYWORD("blend", BLEND, UNRESERVED_KEYWORD, BARE_LABEL)` in alphabetical position. `kwlist.h` is the single source of truth: `scan.l` does NOT need a touch for a new keyword (only new token *shapes* require lexer edits).
- `src/backend/parser/gram.y` — add `BLEND` to the `%token <keyword>` block AND list it under the matching keyword-category rule (`unreserved_keyword`). If you skip the gram.y category list, bison still tokenizes it but it won't be usable where the rule expects it.

## 2. Grammar rule

- `src/backend/parser/gram.y` — add the production `BlendStmt: BLEND qualified_name INTO qualified_name { $$ = makeNode(BlendStmt); ... @1 location; ... }`. Wire it into the `stmt:` alternation. Use `DropStmt` or `VariableSetStmt` as a template — don't reinvent helpers if `parser/parse_utilcmd.c` already has one.

## 3. Parse node

- `src/include/nodes/parsenodes.h` — define `typedef struct BlendStmt { NodeTag type; RangeVar *target; RangeVar *source; ParseLoc location; } BlendStmt;`. First field MUST be `NodeTag type;`; last field for top-level stmts is conventionally `ParseLoc location;`. `parsenodes.h` is already in `gen_node_support.pl`'s `@all_input_files` list (`gen_node_support.pl:53-77`), so the `T_BlendStmt` tag is generated automatically into `nodes/nodetags.h` — **do not hand-edit nodetags.h**.

## 4. Analyze

- `src/backend/parser/analyze.c` — write `static Query *transformBlendStmt(ParseState *pstate, BlendStmt *stmt)` and add a case for `T_BlendStmt` in the `switch (nodeTag(parseTree))` inside `transformStmt` (analyze.c:334-451, switch at :368).
- **Caution at analyze.c:363-367**: every change to that switch must be reflected in two more places — `stmt_requires_parse_analysis()` (:469-505) and `analyze_requires_snapshot()` (:513-529). Three sites, one logical change; miss any and the plancache silently miscompares.

## 5. Auto-generated copy/equal/out/read/jumble

These come for free from `gen_node_support.pl` (re-run automatically by ninja/make). After the build, inspect the generated chunks for `BlendStmt` in `copyfuncs.funcs.c`, `equalfuncs.funcs.c`, `outfuncs.funcs.c`, `readfuncs.funcs.c`, `queryjumblefuncs.funcs.c`. If anything looks wrong, fix with `pg_node_attr(...)` on the struct or per-field annotations (`equal_ignore`, `query_jumble_ignore`, `query_jumble_location`, etc.; full list in `nodes.h:43-125`).

## 6. nodeFuncs.c

`BlendStmt` is a top-level statement, not an expression node, so the giant `exprType` / `exprTypmod` / `exprCollation` / `exprLocation` / `expression_tree_walker_impl` switches in `nodeFuncs.c` do NOT need cases. If your statement holds child expression trees, walkers will reach them via the generic Query/RangeTblEntry traversal (`query_tree_walker_impl`).

## 7. catversion

- **No bump** if `BlendStmt` is an in-flight parse-tree object only (planned then thrown away). The skill rule: bump `CATALOG_VERSION_NO` in `src/include/catalog/catversion.h` only when a new/changed node can land in a *stored* tree (rule actions, view definitions, `pg_rewrite.ev_action`). For a new MERGE-shaped DML, the statement itself is usually not stored, but if a view or rule can be written using it then yes — bump.
- Adding a new node tag also renumbers existing `T_*` values, so do a full clean rebuild (`--enable-depend` helps). Node numbers never go to disk, so no initdb required for the tag renumbering itself.

## 8. Test

- Add `src/test/regress/sql/blend.sql` + matching `expected/blend.out`, register in `src/test/regress/parallel_schedule`.
- Enable the round-trip GUCs via `PG_TEST_INITDB_EXTRA_OPTS`: `debug_copy_parse_plan_trees=on`, `debug_write_read_parse_plan_trees=on`, `debug_raw_expression_coverage_test=on`. These exercise `copyObject`/`stringToNode(nodeToString())` over every parse and plan tree the regression suite produces.

## 9. Smoke

```
cd dev/build-debug && ninja && meson test --suite regress -q
```
