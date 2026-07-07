# Node shapes — parse-tree (parsenodes.h) vs Expr (primnodes.h)

PG has two distinct "node shapes" depending on which tree the node
lives in. Picking the wrong one for a new feature commits you to 5×
more walker integration work and harder review. The choice is binary
and irreversible without re-doing every walker.

The two shapes:

- **Parse-tree node** — first field is `NodeTag type;`. Lives in
  `src/include/nodes/parsenodes.h`. Visited by `transformExprRecurse`
  and rewritten into an Expr node before the planner runs.
- **Expr-flavored node** — first field is `Expr xpr;` (which itself
  embeds `NodeTag` via `Expr → Node`). Lives in
  `src/include/nodes/primnodes.h`. Participates in expression-tree
  evaluation throughout the planner + executor + JIT.

The shape determines how many walkers must learn about your node:
parse-tree nodes need only `transformStmt` routing plus auto-generated
copy/eq/out/read; Expr nodes need cases in `nodeFuncs.c` (6+ functions),
`parse_collate.c`, `ruleutils.c`, plus a JIT mirror — usually 5× more
sites than a parse-tree-only node.

Origin: sesvars Phase 0/1 (2026-06-17). Sesvars v1 added a parse-tree
node `SessionVarRef` (NodeTag-direct) AND a separate Expr node
`SessionVar` (Expr-flavored), with `transformExprRecurse` lowering the
former to the latter — clean parse/post-analysis separation, but the
Expr node multiplied the walker work. The user's reference
implementation took a different path: reuse `Param` with a new
`PARAM_SESSION_VARIABLE` kind, no new Expr node at all. Both are valid
designs; the trade-off table is at the end of this file.

Anchors:
- `source/src/include/nodes/parsenodes.h:321-326` — `ParamRef`, the
  canonical NodeTag-direct parse-tree node [verified-by-code]
- `source/src/include/nodes/primnodes.h:391-405` — `Param`, the
  canonical Expr-flavored post-analysis node [verified-by-code]
- `source/src/include/nodes/primnodes.h:357-389` — comment block
  explaining the `ParamKind` enum and the `ParamRef → Param` transform
  [from-comment]
- `source/src/backend/parser/parse_expr.c:139-156` —
  `transformExprRecurse` lowering `ParamRef → Param` [verified-by-code]

## The two shapes side-by-side

[verified-by-code `source/src/include/nodes/parsenodes.h:321-326`]:

```c
typedef struct ParamRef
{
    NodeTag     type;       /* first field is bare NodeTag */
    int         number;     /* the number of the parameter */
    ParseLoc    location;   /* token location, or -1 if unknown */
} ParamRef;
```

[verified-by-code `source/src/include/nodes/primnodes.h:391-405`]:

```c
typedef struct Param
{
    pg_node_attr(custom_query_jumble)

    Expr        xpr;            /* first field is Expr (which embeds NodeTag) */
    ParamKind   paramkind;      /* kind of parameter. See above */
    int         paramid;        /* numeric ID for parameter */
    Oid         paramtype;      /* pg_type OID of parameter's datatype */
    int32       paramtypmod;
    Oid         paramcollid;
    ParseLoc    location;
} Param;
```

Three observable differences:

1. **First field**: `NodeTag type` vs `Expr xpr`. The `Expr xpr` form is
   required if you want the node to participate in expression evaluation
   (the executor casts nodes to `Expr *` and reads `xpr.type` via the
   embedded NodeTag).
2. **Carried metadata**: parse-tree nodes carry only what came from the
   parser (the literal SQL token's identity + `ParseLoc`). Expr nodes
   carry the analyzer's output: type OID, typmod, collation.
3. **Field naming**: Expr nodes prefix every field with the node-name
   root (`paramkind`, `paramid`, `paramtype`) to dodge Objective-C /
   Win32 reserved identifiers — see `portable-identifiers.md`.

## When to use which

| Phase | Shape | Example |
|---|---|---|
| Raw parse tree (post-`raw_parser`, pre-`parse_analyze_*`) | parse-tree (NodeTag-direct) | `ParamRef`, `ColumnRef`, `A_Const`, `A_Expr` |
| Post-analysis (rewritten Query) through end of executor | Expr-flavored (`Expr xpr;`) | `Param`, `Var`, `Const`, `OpExpr`, `FuncExpr` |

The cutoff is `transformExprRecurse`. Once an expression has gone through
the analyzer, every Expr-shaped slot in a Query tree must hold an
Expr-flavored node. Anything still in parse-tree shape after analysis is
either a bug or a feature that intentionally postpones analysis (rare —
e.g. RAW utility statements that don't analyze).

The decision tree:

- Does the node only ever appear in the raw parse tree (pre-analysis)
  and get rewritten away during transformation? → **parse-tree node**
  in `parsenodes.h`.
- Does the node appear in post-analysis Query trees, planner trees,
  executor expression evaluation, or stored views/rules? →
  **Expr-flavored node** in `primnodes.h`.
- Is it a utility statement (DDL, COPY, EXPLAIN)? → parse-tree node in
  `parsenodes.h`; utility statements never become Expr trees.

The canonical pair `ParamRef → Param` demonstrates the pattern: SQL
`$1` is parsed as `ParamRef{number=1}` (parse-tree shape, no type
info yet); `transformParamRef` looks up the param's type from the
ParseState and emits a `Param{paramkind=PARAM_EXTERN, paramid=1,
paramtype=<oid>, ...}` (Expr-flavored, fully typed) which the planner
+ executor can evaluate.

## The transform pattern

`transformExprRecurse` is the dispatcher
[verified-by-code `source/src/backend/parser/parse_expr.c:139-156`]:

```c
static Node *
transformExprRecurse(ParseState *pstate, Node *expr)
{
    ...
    switch (nodeTag(expr))
    {
        case T_ColumnRef:
            result = transformColumnRef(pstate, (ColumnRef *) expr);
            break;
        case T_ParamRef:
            result = transformParamRef(pstate, (ParamRef *) expr);
            break;
        case T_A_Const:
            ...
    }
    ...
}
```

`transformParamRef` (same file) reads the parse-tree `ParamRef`,
consults `pstate->p_paramref_hook` or the externally supplied param
type list, and constructs a `Param` Expr node carrying the resolved
type info. The original `ParamRef` is discarded.

For a new feature `@sesvar`, the parallel structure would be:

```c
/* parse-tree node */
typedef struct SessionVarRef
{
    NodeTag     type;
    char       *name;
    ParseLoc    location;
} SessionVarRef;

/* Expr-flavored node */
typedef struct SessionVar
{
    Expr        xpr;
    char       *name;
    Oid         vartype;        /* NOT typeid — see portable-identifiers.md */
    int32       vartypmod;
    Oid         varcollid;
    ParseLoc    location;
} SessionVar;

/* in transformExprRecurse: */
case T_SessionVarRef:
    result = transformSessionVarRef(pstate, (SessionVarRef *) expr);
    break;

/* transformSessionVarRef looks up the sesvar's current type and emits
   a SessionVar Expr node */
```

This is the pattern sesvars v1 followed. It's the textbook approach and
maps cleanly onto every PG idiom — but see "The alternative" below.

## Walker coverage requirements per shape

The shape choice dictates how many sites need updating. Approximate
count from sesvars Phase 0-7:

### Parse-tree node (NodeTag-direct in `parsenodes.h`)

- `transformExprRecurse` routing (1 case)
- `gen_node_support.pl` auto-regenerates `_copy*`, `_equal*`,
  `_out*`, `_read*`, `_jumble*` from the struct definition — zero hand
  code if no `pg_node_attr(custom_*)` is set
  [verified-by-code `source/src/backend/nodes/gen_node_support.pl`]
- Optional: ECPG preprocessor (if the new node can appear in embedded
  SQL — rare)

**Total: ~1 hand-edited site.**

### Expr-flavored node (`Expr xpr;` in `primnodes.h`)

- `transformExprRecurse` routing (1 case) — for any parse-tree
  predecessor node it lowers from
- `expression_tree_walker` arm in `nodeFuncs.c` (1 case)
- `expression_tree_mutator` arm in `nodeFuncs.c` (1 case)
- `exprType` arm in `nodeFuncs.c` (1 case)
- `exprTypmod` arm in `nodeFuncs.c` (1 case)
- `exprCollation` / `exprSetCollation` arms in `nodeFuncs.c` (2 cases)
- `exprLocation` arm in `nodeFuncs.c` (1 case)
- `parse_collate.c assign_collations_walker` arm (1 case)
- `ruleutils.c get_rule_expr` arm — without this, `EXPLAIN VERBOSE`
  and `pg_get_viewdef` silently break (sesvars F14)
- JIT mirror in `jit/llvm/llvmjit_expr.c` (if the node participates in
  ExecInterpExpr — every Expr node effectively does, via
  `ExecInitExprRec`)
- ExecEvalExpr step setup in `execExpr.c` — for the runtime evaluation
- Possibly `pg_node_attr(custom_query_jumble)` + a custom jumble
  function in `queryjumblefuncs.c` (the `Param` node carries this
  attr) [verified-by-code `source/src/include/nodes/primnodes.h:393`]

**Total: ~10-15 hand-edited sites.**

The 5× multiplier isn't an exaggeration; sesvars Phase 0-7 spent more
time on the Expr-node walker coverage than on the actual semantics.

## The alternative: reuse an existing Expr node

For features whose runtime behavior fits inside an existing Expr node's
shape, **don't add a new Expr node** — extend the existing one with a
new kind/discriminator.

`Param` is the prime candidate because:

- It already carries `paramkind` (an enum) — adding a new value
  (`PARAM_SESSION_VARIABLE`, `PARAM_GUC`, etc.) is one line in
  `ParamKind` plus the executor arm to look up the runtime value.
- It already has `paramtype` / `paramtypmod` / `paramcollid` slots.
- It already has every walker arm in `nodeFuncs.c`,
  `ruleutils.c get_rule_expr`, JIT, `parse_collate.c`,
  `queryjumblefuncs.c`.
- It already participates in the plan-cache / generic-vs-custom plan
  machinery.

Sesvars' user-reference implementation took this route: a new
`PARAM_SESSION_VARIABLE` paramkind on the existing `Param` node, plus a
side index keyed by name for lookup. Zero new walker sites. The trade-off
is conceptual coherence — a `Param` named "@x" is a slight stretch on
"parameter" semantics — but the implementation surface drops 5×.

Decision rule:

- New Expr behavior fits an existing kind discriminator + the existing
  field set? → **Reuse**, add a kind value.
- New Expr behavior needs fields the existing node doesn't have, OR is
  semantically far enough that overloading the existing kind would
  confuse reviewers? → **New Expr node**, accept the walker tax.

Sesvars v1 (AI-implemented) chose new node; the manual reference chose
reuse. Both work. The v1 retrospective concluded reuse would have been
cheaper — see
`postgresql-dev-feature-sesvars/planning/sesvars/comparison.md` for the
full comparison.

## Why the Expr embedding matters at runtime

The executor's expression evaluation (`ExecInterpExpr`, JIT'd or
interpreted) doesn't switch on `NodeTag` at the leaf — it walks a
pre-compiled `ExprState`/`ExprEvalStep` array. But:

- `ExecInitExprRec` (in `execExpr.c`) DOES switch on the source node's
  `NodeTag` to emit the right `EEOP_*` step. Every Expr node needs an
  arm there.
- `parse_collate.c` walks expression trees and switches on NodeTag to
  read each Expr node's collation slot. Without an arm, the
  collation-propagation pass either ignores your node (might be fine)
  or hits a default-case ERROR (depends on the walker).
- `ruleutils.c get_rule_expr` is the deparse function. EXPLAIN VERBOSE,
  `pg_get_viewdef`, `pg_get_ruledef`, error context callbacks all use
  it. Without an arm, your Expr node deparses as garbage or hits an
  assertion. **This is the silent-failure mode** — there's no test
  that exercises every Expr × every deparse use unless you write one
  (see R14 in `pg-implement-discipline.md`).

The minimum acceptance test for "I added an Expr node" is:

```sql
PREPARE p AS SELECT <new-node-expr> AS c1;
EXPLAIN VERBOSE EXECUTE p;
CREATE VIEW v AS SELECT <new-node-expr> AS c1;
SELECT pg_get_viewdef('v');
```

If either deparse path returns garbage or errors, `ruleutils.c` is
missing an arm.



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| `src/backend/nodes/gen_node_support.pl` | — | gen_node_support.pl auto-regenerates _copy, _equal, _out, _read, _jumble from the struct definition — zero... |
| [`src/backend/parser/parse_expr.c`](../files/src/backend/parser/parse_expr.c.md) | 139 | transformExprRecurse lowering ParamRef → Param |
| [`src/backend/parser/parse_expr.c`](../files/src/backend/parser/parse_expr.c.md) | — | transformExprRecurse pattern |
| [`src/include/nodes/parsenodes.h`](../files/src/include/nodes/parsenodes.h.md) | 321 | ParamRef, the canonical NodeTag-direct parse-tree node |
| [`src/include/nodes/parsenodes.h`](../files/src/include/nodes/parsenodes.h.md) | — | parse-tree node home |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 357 | comment block explaining the ParamKind enum and the ParamRef → Param transform |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 391 | Param, the canonical Expr-flavored post-analysis node |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 393 | Possibly pg_node_attr(custom_query_jumble) + a custom jumble function in queryjumblefuncs.c (the Param... |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | — | Expr node home |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/node-types-and-lists.md` — the underlying NodeTag
  / List machinery both shapes depend on
- `knowledge/idioms/portable-identifiers.md` — field-naming discipline
  that applies to both shapes but bites Expr nodes harder
- `knowledge/idioms/query-tree-walkers.md` — the walker functions that
  must learn about your node
- `knowledge/idioms/expression-evaluator-flow.md` — runtime side of
  Expr evaluation
- `knowledge/idioms/jit-expression-codegen.md` — JIT mirror obligations
- `source/src/include/nodes/parsenodes.h` — parse-tree node home
- `source/src/include/nodes/primnodes.h` — Expr node home
- `source/src/backend/parser/parse_expr.c` — `transformExprRecurse`
  pattern

## Open questions / unverified

- Whether there's a precedent for a node that's both parse-tree AND
  Expr-flavored (i.e. carries both `NodeTag type` and `Expr xpr`)
  [unverified] — none seen in current PG. The clean separation appears
  to be the convention.
- Whether `gen_node_support.pl` enforces the "first field is NodeTag or
  Expr" invariant [unverified] — it appears to assume it but I haven't
  traced the validation path.
