# Var + Const nodes — parse-tree column references and literals

`Var` and `Const` are the **two most common leaf nodes** in
PostgreSQL's parse and plan trees. A `Var` references a
column (by range-table-index + attribute-number). A `Const`
holds a literal value (Datum + isnull). Every query
expression eventually decomposes to these two plus
functions/operators that consume them. Understanding their
fields is the cost of admission for parser/planner work.

Anchors:
- `source/src/include/nodes/primnodes.h:262-312` — Var
  struct [verified-by-code]
- `source/src/include/nodes/primnodes.h:324-340` — Const
  struct [verified-by-code]
- `knowledge/data-structures/datum-nullabledatum.md` —
  Const holds a Datum
- `.claude/skills/parser-and-nodes/SKILL.md` — companion

## Var — the column reference

```c
typedef struct Var
{
    Expr        xpr;
    int         varno;            /* RT index OR special */
    AttrNumber  varattno;         /* attribute number, 0 = whole-row */
    Oid         vartype;          /* type OID */
    int32       vartypmod;        /* type modifier */
    Oid         varcollid;        /* collation OID */
    Bitmapset  *varnullingrels;   /* OJ-nullable RT indices */
    Index       varlevelsup;      /* subquery: levels up */
    VarReturningType varreturningtype;  /* OLD/NEW for RETURNING */
    Index       varnosyn;         /* syntactic RT index */
    AttrNumber  varattnosyn;      /* syntactic attribute */
    ParseLoc    location;         /* token location */
} Var;
```

[verified-by-code `primnodes.h:262-312`]

The two essential fields:
- **`varno`** — index into the range table (the list of
  relations the query references). 1, 2, 3, ... or a
  special value.
- **`varattno`** — column number within the referenced
  relation. 1, 2, 3, ... or 0 for "whole-row" Vars.

## The special varno values

[verified-by-code `primnodes.h:248, 250-252`]

```c
#define IS_SPECIAL_VARNO(varno)  ((int) (varno) < 0)

#define PRS2_OLD_VARNO  1   /* in rule rewriter */
#define PRS2_NEW_VARNO  2

/* In executor plans, after planner: */
#define INNER_VAR  -1
#define OUTER_VAR  -2
#define INDEX_VAR  -3
#define ROWID_VAR  -4
```

After planning, varno changes meaning:

- **`varno > 0`** — refers to scan-relation's tuple slot.
- **`INNER_VAR` / `OUTER_VAR`** — refers to inner / outer
  child plan node's output.
- **`INDEX_VAR`** — refers to the index tuple (in
  index-only scans).
- **`ROWID_VAR`** — refers to the row identifier (used in
  EPQ rechecks).

So in a Plan tree, `varno` is read with awareness of
which special values are in play.

## Whole-row Vars — varattno = 0

A `Var` with `varattno = 0` represents the **entire row**:

```sql
SELECT mytable.* FROM mytable;
```

vs

```sql
SELECT mytable.col1, mytable.col2, ... FROM mytable;
```

The first produces a whole-row Var (`varattno = 0`); the
second produces individual Vars per column.

Whole-row Vars are typed as RECORD or as the relation's
composite type. They're how `SELECT t.* FROM t` returns
all columns even if more get added later.

## varnullingrels — outer-join nullable tracking

[from-comment `primnodes.h:285-289`]

> RT indexes of outer joins that can replace the Var's
> value with null.

A Var that comes from the OUTER side of a LEFT JOIN may be
NULL even if the underlying tuple isn't (because the join
produces a NULL row when no match exists). The
`varnullingrels` bitmapset records which OJ RT indices can
null-out this Var.

The planner uses this to:
- Decide whether `WHERE var IS NULL` can match
  non-OJ-null rows.
- Determine which Vars are guaranteed non-NULL.

Pre-PG 16 used a simpler `varlevelsup` + `phlevelsup`
approach; the current scheme is more precise.

## varlevelsup — correlated subqueries

For subqueries:
- `varlevelsup = 0` — this Var refers to the current
  query level.
- `varlevelsup = N` — refers to N levels above (outer
  query).

This is how SQL's `SELECT ... FROM t1 WHERE EXISTS (SELECT
... FROM t2 WHERE t2.col = t1.col)` works — the inner
Var `t1.col` has `varlevelsup = 1`.

## Const — the literal value

```c
typedef struct Const
{
    pg_node_attr(custom_copy_equal, custom_read_write)

    Expr        xpr;
    Oid         consttype;
    int32       consttypmod;
    Oid         constcollid;
    int         constlen;         /* see attlen rules */
    Datum       constvalue;
    bool        constisnull;
    bool        constbyval;        /* pass-by-value */
    ParseLoc    location;
} Const;
```

[verified-by-code `primnodes.h:324-340`]

The essentials:
- **`consttype`** — pg_type OID.
- **`constvalue`** — Datum holding the value.
- **`constisnull`** — true if NULL.
- **`constbyval`** — pass-by-value vs pointer.

## The varlena restriction on Const

[from-comment `primnodes.h:317-321`]

> for varlena data types, we make a rule that a Const
> node's value must be in non-extended form (4-byte header,
> no compression or external references). This ensures
> that the Const node is self-contained and makes it more
> likely that equal() will see logically identical values
> as equal.

Every Const carrying a varlena (text, jsonb, etc.) MUST
hold the long-header form. Short-headers, compressed forms,
and TOAST pointers are forbidden in Const nodes.

This is the "Consts are self-contained" invariant. Code
constructing a Const from a possibly-toasted value must
detoast first.

## NULL Consts

`constisnull = true` + `constvalue = (Datum) 0`. The
`constvalue` field is undefined in this case. Always check
`constisnull` first.

NULL Consts of different types differ in `consttype` —
`NULL::int` and `NULL::text` are distinct Const nodes.

## The query_jumble system

[from-comment `primnodes.h:286-287, 301-303`]

For `pg_stat_statements`-style query normalization,
`equal_ignore` and `query_jumble_ignore` annotations skip
certain fields:
- `varnullingrels` skipped (semantically determined).
- `varnosyn` / `varattnosyn` skipped (syntactic).
- `vartype`, `vartypmod`, `varcollid` skipped (type-only).

This lets `SELECT a FROM t WHERE b = 1` and `SELECT a FROM
t WHERE b = 2` produce the same query identifier.

## Common review-time concerns

- **`varno` semantics differ pre/post-plan.** Code touching
  Vars must know which phase.
- **`varattno = 0` is whole-row** — check before
  attribute-indexing.
- **`varlevelsup > 0` indicates correlation** — subquery
  pull-up has special handling.
- **Consts must be self-contained** for varlena types —
  detoast before constructing.
- **`varnullingrels` matters for outer-join semantics** —
  changing it without understanding the OJ topology is
  bug-prone.

## Invariants

- **[INV-1]** `varno` is either a positive RT index, a
  special negative constant, or 1/2 (rule rewriter).
- **[INV-2]** `varattno = 0` means whole-row Var.
- **[INV-3]** `varlevelsup > 0` indicates correlated outer
  reference.
- **[INV-4]** Const must hold non-extended varlena form;
  no TOAST pointers.
- **[INV-5]** `varnullingrels` records which outer joins
  can null this Var.

## Useful greps

- All Var producers:
  `grep -RIn 'makeVar\b' source/src/backend | head -10`
- All Const producers:
  `grep -RIn 'makeConst\b' source/src/backend | head -10`
- Special varno usage:
  `grep -RIn 'INNER_VAR\|OUTER_VAR\|INDEX_VAR\|ROWID_VAR' source/src/backend | head -20`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/nodes/makefuncs.c`](../files/src/backend/nodes/makefuncs.c.md) | — | makeVar / makeConst constructors |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 262 | Var struct |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | 324 | Const struct |
| [`src/include/nodes/primnodes.h`](../files/src/include/nodes/primnodes.h.md) | — | full type definitions |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/data-structures/datum-nullabledatum.md` —
  Const holds a Datum.
- `knowledge/data-structures/fmgrinfo.md` — function calls
  in expression trees use FmgrInfo.
- `knowledge/idioms/expression-evaluator-flow.md` — the
  evaluator processes Var + Const at runtime.
- `.claude/skills/parser-and-nodes/SKILL.md` — parse-tree
  conventions.
- `.claude/skills/executor-and-planner/SKILL.md` —
  planner manipulates Vars + Consts.
- `source/src/include/nodes/primnodes.h` — full type
  definitions.
- `source/src/backend/nodes/makefuncs.c` — `makeVar` /
  `makeConst` constructors.
