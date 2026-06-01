---
name: parser-and-nodes
description: Operational checklist for editing the PostgreSQL parser (scan.l / gram.y / analyze.c) and for adding or modifying a Node type used in parse / plan / executor trees. Use whenever the change touches `src/backend/parser/**`, `src/include/nodes/*.h`, or anything that requires re-running `gen_node_support.pl`.
---

# Parser & Node-types — operational

Companion docs: `knowledge/idioms/parser-pipeline.md`, `knowledge/idioms/node-types-and-lists.md`.

## When you're adding a new SQL statement

Touch four layers, in order. Build between each so you fail fast.

1. **Grammar — `src/backend/parser/gram.y`**
   - Add the keyword(s) to `unreserved_keyword` / `col_name_keyword` / etc. AND to `src/include/parser/kwlist.h` (alphabetical, with category).
   - Add a top-level rule producing your new `*Stmt` node, wire it into `stmt:` (search for `stmt:` in `gram.y`). Use `makeNode(FooStmt)` in the action, set the location with `@1`, fill fields from `$N`.
   - Match an existing simple statement as template (e.g. `DropStmt`, `VariableSetStmt`). Do NOT invent fresh helpers in gram.y if `parser/parse_utilcmd.c` already has one.

2. **Lexer — `src/backend/parser/scan.l`** *(only if you introduced a new token shape; new keywords alone do not need scan.l changes — they go through `kwlist.h`)*.

3. **Parse node — `src/include/nodes/parsenodes.h`** *(utility stmts)* or `primnodes.h` *(expressions)* or `plannodes.h` *(plan nodes)*
   - First field `NodeTag type;` (or another node struct, for "inheritance").
   - Last field for top-level statements is typically `ParseLoc location;`.
   - Annotate fields if needed: `pg_node_attr(...)` on the struct, per-field attrs like `query_jumble_ignore`, `equal_ignore`. See `nodes.h:43-125` for the full list.

4. **Analyze / execute**
   - Optimizable statement → add a `transformFooStmt(ParseState *, FooStmt *)` in `parser/analyze.c` and wire it into the `switch (nodeTag(parseTree))` inside `transformStmt` (analyze.c:368).
   - Utility statement → no transform needed; just dump into a Query with `CMD_UTILITY` (the default path). Execution lives in `src/backend/commands/` via `ProcessUtility` / `standard_ProcessUtility` (`src/backend/tcop/utility.c`).

5. Run `gen_node_support.pl` (done automatically by the build) and verify the generated `copyfuncs.funcs.c`, `equalfuncs.funcs.c`, `outfuncs.funcs.c`, `readfuncs.funcs.c` chunks for your new struct look sane.

6. Add a regression test under `src/test/regress/sql/` (and a matching expected file). See `.claude/skills/testing/SKILL.md`.

## When you're adding a new Node type (no SQL change)

From `src/backend/nodes/README` "Steps to Add a Node":

1. Put the struct in the right header. The file must be in `gen_node_support.pl`'s `@all_input_files` list (parsenodes.h, primnodes.h, plannodes.h, pathnodes.h, execnodes.h, value.h, etc. — see `gen_node_support.pl:53-77`). The `T_Foo` tag is generated automatically into `nodes/nodetags.h` (do NOT hand-edit it).
2. First field is `NodeTag type;` — unless you "inherit" by embedding another node struct as the first field (e.g. `Plan plan;` in a new plan node).
3. Build. Inspect the generated `copyfuncs.funcs.c` / `equalfuncs.funcs.c` / `outfuncs.funcs.c` / `readfuncs.funcs.c` / `queryjumblefuncs.funcs.c` entries for your node. Add `pg_node_attr(...)` and per-field attrs to fix anything wrong.
4. If a field needs special treatment, common annotations:
   - `pg_node_attr(custom_copy_equal)` — write your own bodies in `copyfuncs.c` / `equalfuncs.c` and the generator will skip yours.
   - `pg_node_attr(no_copy_equal, no_read, no_query_jumble)` — opt out entirely (executor state nodes typically use `nodetag_only`).
   - Per-field: `array_size(otherfield)`, `copy_as(VALUE)`, `equal_ignore`, `read_write_ignore`, `query_jumble_ignore`, `query_jumble_location`.
5. Add cases to `nodeFuncs.c` (`expression_tree_walker_impl`, `expression_tree_mutator_impl`, `raw_expression_tree_walker_impl`) if your node holds child expressions/plans that walkers must descend into. Grep for a sibling node type to find every place that needs touching.
6. **Adding a node type renumbers existing tags.** Recompile the whole tree (`--enable-depend` helps). No initdb needed — node numbers never go to disk. BUT if the node can appear in a *stored* parse tree (rule actions, view definitions), bump `CATALOG_VERSION_NO` in `src/include/catalog/catversion.h`.
7. Test with `debug_copy_parse_plan_trees=on`, `debug_write_read_parse_plan_trees=on`, `debug_raw_expression_coverage_test=on` (set via `PG_TEST_INITDB_EXTRA_OPTS`).

## When you're modifying an existing Node type

- **Adding a field** to a node that appears in stored catalog parse trees (e.g. `Query`, anything in views / rules) → bump catversion. Add a `pg_node_attr` if the new field needs special read/write handling (e.g. `read_as(...)` for backward-compat when reading old serialized trees from extensions — usually not needed because catversion changes invalidate stored trees).
- **Removing or reordering fields** → also catversion bump if stored.
- **Changing only Plan/Path internal fields** (never serialized to catalogs) → no catversion bump needed. But Plan nodes ARE serialized to parallel workers, so you still need correct out/read funcs.

## Pre-submit smoke

```
cd dev/build-debug && ninja && \
  meson test --suite regress -q
```

Plus the debug-tree GUCs above on a separate initdb if you touched anything tree-shape related.

## Files-examined rows

| file | depth | produced |
| --- | --- | --- |
| `src/backend/parser/README` | full | SKILL §"new SQL statement" |
| `src/backend/parser/gram.y` lines 13625-13706 | scanned + 1 rule | SKILL §grammar |
| `src/backend/parser/scan.l` 1-40 | top | SKILL §lexer |
| `src/backend/parser/parse_node.c` 1-50 | top | SKILL §analyze |
| `src/backend/parser/analyze.c` 1-80, 334-433 | transformStmt full switch | SKILL §analyze |
| `src/backend/nodes/README` | full | SKILL §"new Node" |
| `src/include/nodes/nodes.h` | full | SKILL §annotations |
| `src/include/nodes/pg_list.h` 1-120, 380-485 | List API + foreach | idioms |
| `src/include/nodes/value.h` | full | idioms |
| `src/backend/nodes/gen_node_support.pl` 1-140 | top + file list | SKILL §generator |
