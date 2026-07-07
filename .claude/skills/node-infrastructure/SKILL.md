---
name: node-infrastructure
description: PostgreSQL's Node type system — the tagged-union polymorphism used for parser output (Query, RangeTblEntry), planner output (Path, Plan), executor state (PlanState, ExprState), and every intermediate representation. Covers `src/backend/nodes/gen_node_support.pl` (the code generator) + `src/include/nodes/*.h` + the copy/equal/out/read function families + walker/mutator support (`nodeFuncs.c`). Loads when the user asks about `NodeTag`, adding a new Node type (has scenario `add-new-node-type`), `expression_tree_walker` / `expression_tree_mutator`, why grammar changes require regenerating `nodes.h`, the `T_Foo` enum, or `castNode` / `nodeTag` macros. Skip when the ask is about a specific Node (e.g. SeqScan, HashJoin) — those live under executor/optimizer skills.
when_to_load: Add a new Node type; touch gen_node_support.pl; understand tree walker/mutator patterns; debug node-serialization bugs (copy/equal/out/read).
companion_skills:
  - parser-and-nodes
  - executor-and-planner
---

# node-infrastructure — the Node type system

PG uses a **tagged union** pattern for every intermediate representation: parse tree, query tree, plan tree, execution state. Each node is a struct starting with `NodeTag type;` (an enum value); code that operates on trees switches on `type` to dispatch.

This is what enables `expression_tree_walker` and `expression_tree_mutator` to traverse and transform trees generically — they use the tag to look up per-node behavior.

## The file map

| File | Role |
|---|---|
| `src/backend/nodes/gen_node_support.pl` | **The code generator.** Reads `parsenodes.h` / `primnodes.h` / `plannodes.h` / etc., parses the Node struct definitions, produces: |
| `src/backend/nodes/copyfuncs.c` (generated) | `copyObjectImpl(node)` — deep-copy every Node struct. Big switch on NodeTag. |
| `src/backend/nodes/equalfuncs.c` (generated) | `equal(a, b)` — deep equality. Big switch. |
| `src/backend/nodes/outfuncs.c` (generated) | Serialize Node tree to text — for `nodeToString` + WAL / stored plans / debug. |
| `src/backend/nodes/readfuncs.c` (generated) | Deserialize text back to Node tree — `stringToNode`. |
| `src/backend/nodes/nodes.c` | Small hand-written companion — `newNode` macro internals. |
| `src/backend/nodes/nodeFuncs.c` | Tree walkers + mutators + type-classification predicates (`exprType`, `IsA`, etc.). |
| `src/include/nodes/nodes.h` (generated) | The `NodeTag` enum — one `T_<TypeName>` per Node. |

## The `T_` enum

`NodeTag` is a big enum:

```c
typedef enum NodeTag {
    T_Invalid = 0,
    T_IndexInfo,
    T_ExprContext,
    T_Query,
    T_RangeTblEntry,
    T_TargetEntry,
    T_Var,
    T_Const,
    T_Param,
    ...
    T_SeqScan,
    T_HashJoin,
    T_Agg,
    ...
    T_SortState,
    T_HashState,
    ...
    T_XxxStmt,
} NodeTag;
```

Adding a new Node = adding a new enum value + a struct definition. `gen_node_support.pl` regenerates all the support files from the struct definitions.

## The Node struct pattern

```c
typedef struct MyNewNode {
    Node xpr;         /* MUST be first for Expr subclasses */
    /* OR */
    NodeTag type;     /* MUST be first for plain Node subclasses */

    /* fields */
    Oid    myoid;
    List  *mylist;
    /* etc */
} MyNewNode;
```

The first field is a discriminator. `Expr`-subtype nodes start with `Expr xpr` (which itself starts with `NodeTag type`), enabling the tree-walker infrastructure to know "this is an Expr" without further checks.

## Generated code — what gen_node_support.pl does

For a Node struct like:

```c
typedef struct SomeNode {
    NodeTag type;
    Node   *someChild;
    List   *someList;
    Oid    someOid;
    /* pg_node_attr(...) attributes */
} SomeNode;
```

`gen_node_support.pl` produces four function bodies:

1. **Copy** (in copyfuncs.c) — allocates a new SomeNode, recursively copies each field.
2. **Equal** (in equalfuncs.c) — recursively compares each field.
3. **Out** (in outfuncs.c) — writes `{SOMENODE :someChild ... :someList ... :someOid ...}` text.
4. **Read** (in readfuncs.c) — parses that text back.

You edit the header; the perl script regenerates everything. NEVER hand-edit the generated files.

## `pg_node_attr` attributes

Special annotations on Node fields:

- `pg_node_attr(equal_ignore)` — field skipped in equal(). Useful for cached data.
- `pg_node_attr(read_write_ignore)` — field skipped in out/read. Useful for pointers to non-serializable state.
- `pg_node_attr(copy_as_scalar)` — for opaque fields (function pointers, etc.).
- `pg_node_attr(no_read)` — no read support (only in one direction).

## Tree walkers + mutators

The pattern for tree traversal:

```c
static bool my_walker(Node *node, MyContext *ctx) {
    if (node == NULL) return false;

    /* Check for the specific node types you care about */
    if (IsA(node, Var)) {
        /* Do something with the Var */
    }

    /* Recurse into children */
    return expression_tree_walker(node, my_walker, ctx);
}

/* Call it */
my_walker((Node *) query, &ctx);
```

`expression_tree_walker` knows how to descend into every Node type — that's the payoff of the tagged-union design.

Mutators are similar but return a transformed tree.

## Common patch shapes

### Add a new Node type

Scenario `add-new-node-type` covers this end-to-end. Sequence:

1. Add `T_MyNewNode` to the appropriate section of `nodes.h` (parsenodes / primnodes / plannodes).
2. Add the struct definition to that header.
3. Run `make` — the perl script regenerates copyfuncs/equalfuncs/outfuncs/readfuncs.
4. Wire the new node into whatever hook produces it (parser production, planner rewrite, etc.).
5. Update walkers/mutators if the new node has children that need traversal.
6. Add `IsA` uses at consumer sites.
7. Regress test.

### Change a Node struct field

- Add / rename / remove fields in the header.
- Run `make` — regenerated code adapts.
- Update every hand-written consumer using the field.

### Add a walker case

- Simple: `expression_tree_walker` handles it automatically if the new node's children are in known-walker fields.
- Complex: for uncommon child-field patterns (e.g. `List of custom-struct`), extend the walker in nodeFuncs.c.

### Debug "castNode returned NULL"

- `castNode(SomeType, node)` uses `IsA` — check `node->type == T_SomeType`.
- If NULL: the Node is a different type than you expected. Check upstream production.
- `nodeTag(node)` shows the actual tag.

## Pitfalls

- **NEVER hand-edit generated files** — copyfuncs/equalfuncs/outfuncs/readfuncs are regenerated by gen_node_support.pl. Hand edits get overwritten.
- **`memcpy` a Node = wrong** — use `copyObject` for deep copy. `memcpy` shares child pointers, then double-frees.
- **Adding a Node without walker support** — if you don't extend the walker for a new node's children, tree traversal won't descend. Bugs surface as "planner sees only some Vars, not all".
- **`equal_ignore` on functional-difference fields = subtle bugs** — the equality check is used in cached-plan invalidation, hashing, etc. Ignoring a field that DOES matter for behavior breaks these.
- **`readfuncs.c` version-guarding** — a Node struct changed between PG versions means old serialized plans (e.g. in a plan cache before upgrade) may fail to deserialize. Plan cache reset on major-version upgrade.
- **Node ordering matters for `T_` enum** — enums are dense but sections have historical meaning (parsenodes / primnodes / plannodes are grouped). Don't scatter.
- **NodeTag reuse after deletion is impossible** — a T_ enum value assigned to a removed node CAN'T be reused for a new one, because stored plans might have that tag. Always add new tags at the end of their section.
- **Extensions can register Node types via `T_ExtensibleNode`** — for custom-scan private data + others. Uses `RegisterExtensibleNodeMethods`.

## Related corpus

- **Idiom**: `node-types-and-lists`, `node-types` (Node shapes — parse tree vs Expr).
- **Scenario**: `add-new-node-type` — the definitive patch guide.
- **Subsystem**: `parser-and-rewrite` (parse-tree production), `optimizer` (Plan production), `executor` (PlanState production).
- **Related planning**: `planning/pgstat_progress_leak/` — not directly, but plan-cache bugs often surface through Node serialization.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --scenario add-new-node-type
python3 scripts/corpus-chain.py --file src/backend/nodes/nodeFuncs.c
python3 scripts/corpus-chain.py --idiom node-types-and-lists
```

## Boundary

**Use this skill** for Node type-system + gen_node_support.pl + copy/equal/out/read + walker/mutator.

**Don't use** for:
- **Specific Node types (Var / Const / Plan subtypes)** — see the type's owning subsystem.
- **Grammar changes** — see `parser-and-nodes` skill.
- **Executor state changes** — see `executor-and-planner`.
- **Reading .h files that mention `pg_node_attr`** — the attribute is meaningful only to gen_node_support.pl; consumers ignore it.
