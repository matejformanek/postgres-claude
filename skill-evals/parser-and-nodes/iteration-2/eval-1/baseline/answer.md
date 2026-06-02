# Adding `BLEND <target> INTO <source>`

Walk top-down, building between layers so you catch breakage early.

## 1. Lexer / keyword

- Add `BLEND` to `src/include/parser/kwlist.h` (alphabetical, with category — e.g. UNRESERVED_KEYWORD).
- `src/backend/parser/scan.l` does NOT need editing for a plain new keyword; the lexer reads kwlist via the keyword machinery.

## 2. Grammar

- `src/backend/parser/gram.y` — declare the `BLEND` token, add it to the matching `unreserved_keyword` rule, write a `BlendStmt:` production, and wire it into the top-level `stmt:` alternation. Use an existing simple statement (CopyStmt, DropStmt) as a template.

## 3. Parse node

- Define `BlendStmt` in `src/include/nodes/parsenodes.h`. First field `NodeTag type`; include a `ParseLoc location` if you want error messages to point at the right place.
- The `T_BlendStmt` value will be auto-generated; don't add it by hand to nodetags.h.

## 4. Parse analysis

- Add `transformBlendStmt()` in `src/backend/parser/analyze.c` and wire it into the big `switch (nodeTag(parseTree))` inside `transformStmt`. If your statement is utility (no rewrite/plan), an alternative is to leave it as `CMD_UTILITY` and handle it in `src/backend/commands/` via `ProcessUtility`.

## 5. Generated funcs

- `gen_node_support.pl` runs during the build and generates copy/equal/out/read/jumble functions automatically. Skim the generated files after the build to make sure your struct looks right; use field annotations (`equal_ignore`, `query_jumble_ignore`, etc.) if needed.

## 6. Walker integration

- If `BlendStmt` carries expression sub-trees, you may need to hook into `expression_tree_walker` / `_mutator` in `src/backend/nodes/nodeFuncs.c` — but since this is a top-level statement, the generic Query traversal typically handles it.

## 7. catversion

- Bump `src/include/catalog/catversion.h` only if the node will live in stored catalog trees (views, rules). For a fresh DML-shaped command that's parsed-and-planned each invocation, usually no catversion bump is required. Adding a new node tag also renumbers other tags, so do a clean build.

## 8. Tests

- Add a regression test under `src/test/regress/sql/` and update the schedule.
- Build & run: `meson compile && meson test`.
