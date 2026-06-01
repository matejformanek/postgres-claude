# nodes/ — Node Structures (subsystem README summary)

- **Source:** `source/src/backend/nodes/README` (115 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** deep-read

## Purpose

Postgres uses tagged "Node" types as the universal substrate for parse
trees, plan trees, executor-state trees, and any other object that needs
to flow through `void *`-typed APIs.  This subsystem provides:

1. The taxonomy (`NodeTag` enum) and the macros to instantiate / identify
   / downcast nodes.
2. Auto-generated support functions for copying, equality, serialization,
   deserialization, and query-jumbling — all driven by `gen_node_support.pl`
   scanning the canonical header list.
3. Hand-written specialized containers: `List`, `Bitmapset`, `TIDBitmap`,
   `Params`, `Value` literal wrappers.
4. Tree-introspection helpers (`exprType`, `exprCollation`, walkers,
   mutators) in `nodeFuncs.c`.
5. Extensibility hooks (`extensible.c`) so loadable modules can declare
   new node types.

## Key facts

- Every node struct's first field is `NodeTag type;` (possibly
  transitively, via "inheritance by convention" — embedding another node
  struct as the first field). `[from-README:16-19]`
- Output/read functions are required for node types that appear in
  catalogs (e.g. `pg_rewrite.ev_action`) and for plan-tree nodes that get
  serialized to parallel workers. Executor-state nodes have no copy/equal/
  out/read support. `[from-README:25-32]`
- Inserting/deleting a node type renumbers later tags. Fine in-memory,
  but altering or removing a node type usually demands a CATALOG_VERSION
  bump so stored parse trees can still be re-read. `[from-README:107-115]`

## File inventory (this dir)

Auto-generated (driven by `gen_node_support.pl`):
- `copyfuncs.c` — deep copy dispatch + custom copy for `Const`,
  `A_Const`, `ExtensibleNode`, `Bitmapset`.
- `equalfuncs.c` — equality dispatch + custom equal for the same nodes
  and the List family.
- `outfuncs.c` — `nodeToString` (Lisp-ish text form). Used for catalog
  storage and parallel-worker plan shipping.
- `readfuncs.c` — `stringToNode` (inverse).
- `queryjumblefuncs.c` — `JumbleQuery` produces the 64-bit queryId for
  pg_stat_statements; constants are stripped, lists of constants are
  squashed.

Hand-written:
- `list.c` (40 KB) — the `List` API. Once cons-cells, now an expansible
  array under the cons-cell vocabulary.
- `bitmapset.c` (30 KB) — set of small ints. Heavily used by the planner
  (relids, varattnos, etc.).
- `tidbitmap.c` (44 KB) — TID set for bitmap index scans, with lossy
  fallback when too big.
- `multibitmapset.c` (small) — List-of-Bitmapsets; e.g. for sets of
  (varno, varattno) pairs.
- `makefuncs.c` (23 KB) — `makeFoo(...)` convenience constructors for
  frequently-built node types.
- `nodeFuncs.c` (130 KB) — tree walkers/mutators, `exprType`,
  `exprCollation`, `exprLocation`, etc.
- `nodes.c` — actually not present; `newNode`/`makeNode` are inline in
  `nodes.h`.
- `value.c` (1 KB) — `makeInteger`/`makeString`/etc. for value-wrapper
  nodes.
- `extensible.c` — registry hashtables for extension-defined node types
  and CustomScan methods.
- `params.c` — ParamListInfo helpers.
- `print.c` — debug pretty-printers (`pprint`, `elog_node_display`,
  `print_rt`, `print_tl`, ...).
- `read.c` — `pg_strtok` / `nodeRead` lexer driving `readfuncs.c`.

## Companion headers (`source/src/include/nodes/`)

`nodes.h`, `primnodes.h`, `parsenodes.h`, `pathnodes.h`, `plannodes.h`,
`execnodes.h`, `memnodes.h`, `pg_list.h`, `bitmapset.h`, `tidbitmap.h`,
`extensible.h`, `value.h`, `print.h`, `makefuncs.h`, `nodeFuncs.h`,
`params.h`, `lockoptions.h`, `replnodes.h`, `miscnodes.h`,
`supportnodes.h`, `subscripting.h`, `multibitmapset.h`, `readfuncs.h`,
`queryjumble.h`.

## Adding a node — checklist `[from-README:82-105]`

1. Add the struct to the appropriate `include/nodes/*.h`.
2. Inspect generated `copyfuncs.funcs.c`, `equalfuncs.funcs.c`,
   `outfuncs.funcs.c`, `queryjumblefuncs.funcs.c`,
   `readfuncs.funcs.c`. Add `pg_node_attr(...)` field/struct decorations
   as needed.
3. Add cases in `nodeFuncs.c` for `exprType`, `expression_tree_walker`,
   etc.
4. Test with `debug_copy_parse_plan_trees`,
   `debug_write_read_parse_plan_trees`,
   `debug_raw_expression_coverage_test`.
5. Recompile everything (NodeTag enum renumbers). Bump
   `CATALOG_VERSION_NO` if the node can appear in stored parse trees.

## Cross-references

- Idiom doc: `knowledge/idioms/node-types-and-lists.md` (broader, more
  pattern-oriented).
- The generator: `source/src/backend/nodes/gen_node_support.pl`
  (34 KB Perl script — scans `@all_input_files`, emits `nodetags.h` plus
  the `.funcs.c` / `.switch.c` files).
