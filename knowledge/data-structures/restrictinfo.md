# RestrictInfo — qual-clause wrapper with planner metadata

`RestrictInfo` wraps a single qualification clause (a
`WHERE`/`JOIN` predicate) together with the **derived
metadata the planner needs** to decide where to evaluate
it: which relids it references, whether it can join, its
selectivity, leakproof status, security level, and clone
bookkeeping for outer-join semantics. The clause itself
lives as an Expr in `clause`; everything else is computed
once and cached.

Anchors:
- `source/src/include/nodes/pathnodes.h:2894-2960` —
  RestrictInfo struct head [verified-by-code]
- `source/src/include/nodes/pathnodes.h:2895` —
  `no_read, no_query_jumble` node attrs [verified-by-code]
- `knowledge/data-structures/reloptinfo.md` — companion;
  baserestrictinfo + joininfo are RestrictInfo lists
- `knowledge/data-structures/plannerinfo.md` — companion;
  eq_classes derived from RestrictInfos
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The shape (selected fields)

```c
typedef struct RestrictInfo
{
    pg_node_attr(no_read, no_query_jumble)
    NodeTag       type;

    Expr         *clause;             /* the WHERE / JOIN clause */
    bool          is_pushed_down;     /* pushed-through OJ? */
    bool          can_join;            /* is mergejoin-able? */
    bool          pseudoconstant;     /* evaluates once per query */
    bool          has_clone;
    bool          is_clone;
    bool          leakproof;
    VolatileFunctionStatus has_volatile;
    Index         security_level;

    int           num_base_rels;      /* size of clause_relids - OJ */
    Relids        clause_relids;      /* relids referenced */
    Relids        required_relids;    /* relids needed to evaluate */
    Relids        incompatible_relids;
    Relids        outer_relids;       /* outer-side relids (OJ) */
    Relids        left_relids;        /* binary op LHS */
    Relids        right_relids;       /* binary op RHS */

    Expr         *orclause;           /* clause with sub-RIs (OR only) */

    /* Serial number; equal-clones share */
    int           rinfo_serial;

    /* Selectivity caches */
    Selectivity   norm_selec;
    Selectivity   outer_selec;

    /* Merge-join / hash-join metadata (filled by classification) */
    List         *mergeopfamilies;
    EquivalenceClass *left_ec;
    EquivalenceClass *right_ec;
    EquivalenceMember *left_em;
    EquivalenceMember *right_em;
    List         *scansel_cache;
    bool          outer_is_left;
    Oid           hashjoinoperator;
    Selectivity   left_bucketsize;
    Selectivity   right_bucketsize;
    Selectivity   left_mcvfreq;
    Selectivity   right_mcvfreq;
    Oid           left_hasheqoperator;
    Oid           right_hasheqoperator;
} RestrictInfo;
```

[verified-by-code `pathnodes.h:2894-3000`]

## The dual list location

A RestrictInfo lives in **at least one** of:

- A base rel's `baserestrictinfo` (single-rel quals).
- A join rel's `joininfo` (multi-rel quals).
- A `RestrictInfoList` attached to an EquivalenceClass.
- The PlannerInfo-level `join_info_list` (for outer-join
  identity tracking).

The same RestrictInfo can be referenced from multiple
locations; equality is by pointer identity, NOT by clause
content.

## clause_relids vs required_relids

```c
Relids   clause_relids;     /* relids referenced in the clause */
Relids   required_relids;   /* relids needed to evaluate it */
```

For a simple base-rel qual `t1.x > 5`, these are equal
(`{t1}`). For outer-join clauses, they can differ: a clause
referencing only `t1.x` might require evaluating it at a
specific level due to outer-join nullability.

The planner uses `required_relids` (not `clause_relids`)
to decide eligibility for each scan/join level.

## is_pushed_down — the outer-join discipline

[from-comment `pathnodes.h:2899-2900`]

> true if clause was pushed down in level

A qual originally written ON a higher join level but
pushed below requires `is_pushed_down = true`. The planner
must take care to apply the qual at the right level — too
deep with `is_pushed_down = false` could violate outer-join
NULL semantics.

## has_clone + is_clone — outer-join identity 3

[from-comment `pathnodes.h:2954-2966`]

> When we generate multiple clones of the same qual
> condition to cope with outer join identity 3, all the
> clones get the same serial number. This reflects that we
> only want to apply one of them in any given plan.

For some quals near LEFT JOIN identity-3 reductions, the
planner generates multiple RestrictInfo clones with
different `required_relids` but the **same `rinfo_serial`**.
At plan time it picks exactly one clone per Path; the
serial ensures no double-application.

## can_join — the mergejoin gate

```c
bool          can_join;
List         *mergeopfamilies;
```

`can_join = true` means the clause is a binary equality on
compatible types — a candidate for merge/hash join. The
classification fills `mergeopfamilies` (the btree opfamilies
of the equality) + the EquivalenceClass references for
each side.

`can_join = false` means the clause can still be a join
qual, but only via NestLoop (it can't sort/hash the inner
side on it).

## pseudoconstant — eval once per query

```c
bool          pseudoconstant;
```

A clause containing no Vars (or only `OUTER_VAR` / Const
inputs) evaluates the same for every tuple — once per
query. The planner can hoist it to query start; if false,
short-circuit the whole plan.

## leakproof — security_barrier interaction

```c
bool          leakproof;
```

If the clause's function is leakproof (declared
`LEAKPROOF`), security-barrier views can let it push down
through the barrier. Otherwise, the clause is constrained
to evaluate ABOVE the barrier — the security model
demands it.

The pg_proc.proleakproof attribute drives the value;
non-superuser-callable for setting (it's a security
attestation).

## security_level — pushed-down-through-views level

```c
Index         security_level;
```

Tracks how many security-barrier views the clause has
been pushed through. Used in `baserestrict_min_security`
to ensure quals applied at a scan node respect view
boundaries.

## orclause — the OR sub-Restrictinfo tree

```c
Expr         *orclause;
```

For `(a = 1 OR b = 2)`-style clauses, `orclause` holds a
parallel structure where each arm is itself wrapped as
a RestrictInfo. Lets the planner cost-estimate per arm
(e.g., for BitmapOr planning).

NULL for non-OR clauses.

## Selectivity caches

```c
Selectivity   norm_selec;
Selectivity   outer_selec;
```

The fraction of rows the clause is estimated to pass.
Computed lazily via `clauselist_selectivity`; cached to
avoid recomputation across different join orderings.

`norm_selec` for inner-join contexts; `outer_selec` for
outer-join contexts (the semantics differ for
side-eliminated rows).

## Merge/hash join scratch fields

```c
EquivalenceClass *left_ec, *right_ec;
EquivalenceMember *left_em, *right_em;
Oid           hashjoinoperator;
Selectivity   left_bucketsize, right_bucketsize;
```

For join-eligible RestrictInfos, the planner caches:
- Per-side EquivalenceClass (so EC mechanics can re-use
  the join clause).
- The hash operator (for HashJoin).
- Bucket-size estimates (for hash-join cost model).

These get filled by `process_implied_equality` /
`create_join_clause` before path generation.

## Common review-time concerns

- **Don't compare by clause content** — use pointer
  equality.
- **`required_relids` is what you check** for placement
  eligibility, NOT `clause_relids`.
- **`is_pushed_down` matters** for outer-join correctness.
- **`pseudoconstant` quals short-circuit the plan** when
  false — wire correctly.
- **`leakproof` is a security attestation** — don't
  override.
- **Clones share `rinfo_serial`** — apply exactly one
  per plan path.

## Invariants

- **[INV-1]** `clause` holds the Expr; never NULL except
  for synthetic RIs.
- **[INV-2]** `required_relids` is the placement
  authority.
- **[INV-3]** Clones share `rinfo_serial`; planner picks ≤
  one per path.
- **[INV-4]** `can_join + mergeopfamilies` are the
  merge/hash-join gate.
- **[INV-5]** `leakproof` enforces security-barrier
  semantics.

## Useful greps

- The makers:
  `grep -RIn 'make_restrictinfo' source/src/backend/optimizer | head -10`
- Placement decision:
  `grep -RIn 'required_relids' source/src/backend/optimizer | head -10`
- Clone handling:
  `grep -RIn 'has_clone\|is_clone\|rinfo_serial' source/src/backend/optimizer | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/optimizer/plan/initsplan.c`](../files/src/backend/optimizer/plan/initsplan.c.md) | — | qual classification + distribution |
| [`src/backend/optimizer/util/restrictinfo.c`](../files/src/backend/optimizer/util/restrictinfo.c.md) | — | make_restrictinfo + helpers |
| [`src/include/nodes/pathnodes.h`](../files/src/include/nodes/pathnodes.h.md) | 2894 | RestrictInfo struct head |
| [`src/include/nodes/pathnodes.h`](../files/src/include/nodes/pathnodes.h.md) | 2895 | no_read, no_query_jumble node attrs |
| [`src/include/nodes/pathnodes.h`](../files/src/include/nodes/pathnodes.h.md) | — | full struct |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/data-structures/reloptinfo.md` —
  baserestrictinfo + joininfo are RestrictInfo lists.
- `knowledge/data-structures/plannerinfo.md` — eq_classes
  derive from RestrictInfo membership.
- `knowledge/data-structures/var-const-nodes.md` — clauses
  decompose to Vars + Consts + Op expressions.
- `knowledge/idioms/expression-evaluator-flow.md` —
  ExprState compilation of qual clauses.
- `knowledge/subsystems/optimizer.md` — the planner.
- `.claude/skills/executor-and-planner/SKILL.md` —
  planner conventions.
- `source/src/include/nodes/pathnodes.h` — full struct.
- `source/src/backend/optimizer/util/restrictinfo.c` —
  make_restrictinfo + helpers.
- `source/src/backend/optimizer/plan/initsplan.c` —
  qual classification + distribution.
