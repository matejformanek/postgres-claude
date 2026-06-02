# Adding a BLEND statement — baseline walkthrough

To add a new top-level SQL statement in PostgreSQL you typically need to touch the parser, the node definitions, and the analyze/execute layer.

## Lexer

In `src/backend/parser/scan.l` if you have any new token shapes. For just a keyword you probably don't need to change the lexer — keywords are recognized via a keyword table.

## Keyword table

Add `BLEND` to `src/include/parser/kwlist.h`, in alphabetical order, with the right category (e.g. UNRESERVED_KEYWORD).

## Grammar

In `src/backend/parser/gram.y`:
- Add `BLEND` to the appropriate keyword classification rule.
- Add a new grammar rule, e.g. `BlendStmt: BLEND ... { ... }` that calls `makeNode(BlendStmt)` and fills in fields.
- Wire it into the top-level `stmt:` production.

## Parse node

Define `BlendStmt` in `src/include/nodes/parsenodes.h` with `NodeTag type` as the first field, plus whatever fields you need. The build system auto-generates the copy/equal/out/read functions for it via `gen_node_support.pl` if the file is in its input list.

## Analyze

If BLEND is an optimizable statement (gets planned and executed), add a `transformBlendStmt()` in `src/backend/parser/analyze.c` and add a case to the dispatcher there.

If it's a utility statement (like DDL), there's a default branch that wraps it for utility processing — execution then happens via `ProcessUtility` in `src/backend/tcop/utility.c`, dispatching to something in `src/backend/commands/`.

## Generated funcs

After build, the `gen_node_support.pl` script will produce copy/equal/out/read functions for BlendStmt. You'd want to inspect the output to make sure fields are handled correctly. You can annotate fields if needed (I don't remember the exact attribute syntax — something like `pg_node_attr`).

## Catversion bump

If the new node can appear in stored catalog trees (rule actions, views), you'd need to bump `CATALOG_VERSION_NO` in `src/include/catalog/catversion.h`. For purely transient statements I'm not 100% sure — probably not needed.

## Walkers

You may need to teach `nodeFuncs.c` walkers and mutators about the new node so they recurse into its children — though this is more critical for expression nodes than top-level statements.

## Test

Add a regression test under `src/test/regress/sql/` with a matching `expected/` file.

I don't remember exact line numbers for `transformStmt`'s switch or for the kwlist categories off the top of my head — you'd want to grep for an existing similar statement (e.g. `MergeStmt`) and follow it through every layer to find all the touch points.
