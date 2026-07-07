# Security-barrier views — qual-pushdown prohibition

A view created with `WITH (security_barrier=on)` (or any view
backing RLS-protected access) sets the
`RangeTblEntry.security_barrier` flag. This flag tells the
**planner not to push leaky qualifications through the
subquery boundary**, even if pushdown would be a perf win.
Without the barrier, a user-defined operator that calls
`elog(NOTICE, ...)` on its inputs could leak hidden rows from
inside the view.

Anchors:
- `source/src/backend/rewrite/rewriteHandler.c:1901` —
  security_barrier set on view-expanded RTE [verified-by-code]
- `source/src/include/nodes/parsenodes.h` — RTE flags
- `source/src/backend/optimizer/prep/prepjointree.c` —
  pullup honors security_barrier
- `knowledge/idioms/row-security-policy-application.md` —
  companion (RLS also sets barrier)
- `knowledge/idioms/view-pushdown-via-rewriter.md` — companion
- `knowledge/data-structures/restrictinfo.md` —
  leakproof flag + security_level
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## The flag

[verified-by-code `rewriteHandler.c:1901`]

```c
rte->security_barrier = RelationIsSecurityView(relation);
```

Set when:
- The view was created with `CREATE VIEW ... WITH
  (security_barrier=on)`.
- The view is backing RLS (RLS-protected base table accessed
  through view).

Off when:
- Regular view with normal pushdown semantics.

The flag lives in the RangeTblEntry; carried through analyze →
rewrite → planner.

## Why it matters — the leak vector

Without the barrier, the planner is free to push qualifying
predicates through the subquery boundary if doing so is
cheaper. This is normally safe — the predicate just runs
earlier in the plan.

But a **leaky function** in the predicate could break that:

```sql
CREATE FUNCTION leak(text) RETURNS bool AS $$
BEGIN
    RAISE NOTICE 'saw: %', $1;
    RETURN true;
END $$ LANGUAGE plpgsql STRICT;

CREATE VIEW visible_rows AS
SELECT * FROM secret_table WHERE secret_owner = current_user;

SELECT * FROM visible_rows WHERE leak(secret_col);
```

Without barrier: planner pushes `leak(secret_col)` into the
base scan, calling it on EVERY row of `secret_table` before
the `secret_owner` filter. The NOTICE messages leak all the
hidden rows.

With barrier: `leak()` runs only on rows that already passed
the view's filter; no leak.

## The leakproof attribute

[per `restrictinfo` data-structure doc]

Functions / operators can be declared `LEAKPROOF`:

```sql
CREATE FUNCTION ok(text) RETURNS bool AS $$ SELECT true $$ LEAKPROOF LANGUAGE SQL;
```

Leakproof functions are PROMISED not to leak input information
via error messages, NOTICE / DEBUG output, or other side
channels. The planner CAN push leakproof functions through a
security barrier; it CANNOT push non-leakproof.

Only superusers can mark functions leakproof — it's a security
attestation.

## planner respect — the pushdown decision

[from `optimizer/prep/prepjointree.c`]

When deciding whether to pull up a subquery (inline it into the
outer query) the planner checks:

```c
if (rte->security_barrier && !all_quals_are_leakproof(quals))
    return SUBQUERY_NOT_PULLED_UP;
```

The check is per-qual: leakproof quals can cross the barrier;
non-leakproof must stay outside.

This is finer-grained than "barrier blocks all pullup" —
a barrier still allows leakproof qual pushdown, just not the
leaky kind.

## RestrictInfo.security_level — the layered tracking

```c
typedef struct RestrictInfo {
    ...
    Index security_level;
    ...
} RestrictInfo;
```

`security_level` tracks "this qual has been pushed through N
security barriers". The base level is 0 (top of query). Each
barrier crossed increments by 1.

The planner uses this for:
- `baserestrict_min_security` — minimum security level among
  quals on a base rel; controls plan-tree position.
- Ensuring leaky quals stay above their level boundary.

## CREATE VIEW WITH security_barrier

```sql
CREATE VIEW v WITH (security_barrier=on) AS
    SELECT col FROM t WHERE owner = current_user;
```

Marks the view as a barrier without needing RLS. Useful for:
- Hand-built views over sensitive tables.
- Wrapping a `WHERE` filter you don't want pushed through.
- Performance-tuning escape: barrier = explicit pushdown
  blocker.

## Performance impact

Barriers prevent some optimizations:
- A `WHERE` clause that would have been pushed into an
  IndexScan on the base table stays outside the subquery.
- Join reordering is constrained — the barrier subquery is
  joined at a fixed position.

For RLS-protected queries, this is the cost of safety. For
hand-built barrier views, weigh perf vs leak protection.

## Leakproofness of builtin operators

Most builtin equality / comparison operators (`=`, `<`, `>`)
are leakproof. Functions like `like()`, `regexp_match()`,
`array_position()` are typically NOT — they can call user-
defined comparators or report input details.

`pg_proc.proleakproof` is the canonical source. Check via
`\df+ funcname` in psql.

## Common review-time concerns

- **Barrier doesn't block leakproof pushdown** — finer-grained
  than all-or-nothing.
- **Adding `WITH (security_barrier)` is a perf hit** — confirm
  the protection is needed.
- **proleakproof is a superuser attestation** — don't mark
  PROCEDURAL functions leakproof carelessly.
- **RLS implies barrier** — but inverse not true (barrier
  views without RLS exist).
- **EXPLAIN shows barrier subqueries** as separate scan
  nodes; pullup-inlined views don't appear.
- **Multiple barriers** track via security_level layered
  count.

## Invariants

- **[INV-1]** security_barrier flag set on view RTEs from RLS
  or explicit barrier option.
- **[INV-2]** Leakproof quals can cross barrier; non-leakproof
  cannot.
- **[INV-3]** security_level tracks barrier-crossing depth in
  RestrictInfo.
- **[INV-4]** RLS implies barrier; barrier doesn't imply RLS.
- **[INV-5]** proleakproof is superuser-set; planner trusts
  it.

## Useful greps

- security_barrier consumers:
  `grep -RIn 'security_barrier' source/src/backend/optimizer source/src/backend/rewrite | head -15`
- Leakproof check:
  `grep -RIn 'leakproof\|LEAKPROOF\|proleakproof' source/src/backend/optimizer source/src/backend/catalog | head -10`
- security_level tracking:
  `grep -RIn 'security_level' source/src/backend/optimizer | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/optimizer/prep/prepjointree.c`](../files/src/backend/optimizer/prep/prepjointree.c.md) | — | pullup honors security_barrier |
| [`src/backend/rewrite/rewriteHandler.c`](../files/src/backend/rewrite/rewriteHandler.c.md) | 1901 | security_barrier set on view-expanded RTE |
| [`src/include/catalog/pg_proc.h`](../files/src/include/catalog/pg_proc.h.md) | — | proleakproof column |
| [`src/include/nodes/parsenodes.h`](../files/src/include/nodes/parsenodes.h.md) | — | RTE flags |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md)
- [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md)
- [`add-new-system-view`](../scenarios/add-new-system-view.md)
- [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/view-pushdown-via-rewriter.md` —
  ApplyRetrieveRule sets the flag.
- `knowledge/idioms/row-security-policy-application.md` —
  RLS path that sets it.
- `knowledge/data-structures/restrictinfo.md` — leakproof +
  security_level fields.
- `knowledge/idioms/expression-evaluator-flow.md` —
  ExprState runs the qual after barrier-respect.
- `knowledge/subsystems/optimizer.md` — pullup logic
  in prep/prepjointree.c.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/optimizer/prep/prepjointree.c` —
  pullup honors barrier.
- `source/src/include/catalog/pg_proc.h` — proleakproof
  column.
