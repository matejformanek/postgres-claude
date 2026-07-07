# Row security policy application — RLS in the rewriter

Row-level security (RLS) policies live in `pg_policy`; they're
**applied during query rewrite** by `get_row_security_policies`,
which retrieves all applicable policies for a relation + the
current user + the operation (SELECT / INSERT / UPDATE / DELETE
/ MERGE), then injects them as a synthesized qualifier into the
range-table entry's WHERE clause. Policies can be PERMISSIVE
(OR'd together) or RESTRICTIVE (AND'd on top); the distinction
matters for query semantics.

Anchors:
- `source/src/backend/rewrite/rowsecurity.c:98` —
  get_row_security_policies entry [verified-by-code]
- `source/src/backend/rewrite/rowsecurity.c:715` —
  add_security_quals injection [verified-by-code]
- `knowledge/idioms/view-pushdown-via-rewriter.md` —
  companion (RLS uses similar quals-injection mechanism)
- `knowledge/idioms/security-barrier-views.md` — companion
  (RLS sets security_barrier on the RTE)
- `.claude/skills/executor-and-planner/SKILL.md` — companion

## When it runs

[from-code `rewriteHandler.c`]

In the rewriter, after the basic Query is built:

```c
foreach RTE in query.rtable:
    if (rte points at a table with pg_policy entries
        AND policy applies to this command type):
        get_row_security_policies(query, rte, rti, ...);
        add_security_quals(rti, permissive_quals, restrictive_quals, ...);
```

The output: the RTE's `securityQuals` list is populated with
`Expr` nodes that the planner later wraps the relation scan in.

## Policy retrieval — get_row_security_policies

[verified-by-code `rowsecurity.c:98`]

```c
void
get_row_security_policies(Query *root, RangeTblEntry *rte, int rt_index,
                          List **securityQuals, List **withCheckOptions,
                          bool *hasRowSecurity, bool *hasSubLinks);
```

Walks `pg_policy` for the RTE's relation, filtering by:
- The current user (matched against `pg_policy.polroles`).
- The operation (SELECT / INSERT / UPDATE / DELETE / MERGE) —
  matches against `polcmd` ('r', 'a', 'w', 'd', '*').
- The policy type (`polpermissive` true vs false).

Produces:
- **`*securityQuals`** — list of permissive qual Exprs (will
  be OR'd together) AND restrictive qual Exprs (AND'd at the
  end).
- **`*withCheckOptions`** — for INSERT/UPDATE, the WITH CHECK
  expression to verify after the write.

## PERMISSIVE vs RESTRICTIVE

```sql
CREATE POLICY p1 ON t AS PERMISSIVE FOR SELECT USING (col1 > 0);
CREATE POLICY p2 ON t AS PERMISSIVE FOR SELECT USING (col2 = current_user);
CREATE POLICY p3 ON t AS RESTRICTIVE FOR SELECT USING (col3 < 100);
```

Final qualifier injected: `(col1 > 0 OR col2 = current_user) AND col3 < 100`.

- **PERMISSIVE policies** — disjunction; ANY matching policy
  grants access.
- **RESTRICTIVE policies** — conjunction; ALL must match.

Useful pattern: PERMISSIVE for "users see their own rows or
admin sees all"; RESTRICTIVE for "no one can see archived
rows".

## add_security_quals — the injection

[verified-by-code `rowsecurity.c:715`]

```c
static void
add_security_quals(int rt_index, List *permissive_policies,
                   List *restrictive_policies, List **securityQuals,
                   bool *hasSubLinks);
```

Builds the OR-of-permissives, AND with the restrictives, and
prepends to the RTE's `securityQuals` list.

Each policy's qual is wrapped in a `bool` cast (if needed) and
modified to use the new RTE varno. The final list of Exprs
becomes the security-barrier qual for the relation.

## Interaction with security_barrier

[from-code `rowsecurity.c` + `rewriteHandler.c:1901`]

When `get_row_security_policies` returns non-empty quals, the
RTE is treated as a security-barrier subquery (similar to a
view with `WITH (security_barrier=on)`). This prevents the
planner from pushing **leaky** functions inside the qual
(e.g., a malicious operator that could see rows the policy was
filtering out).

[per `security-barrier-views` companion]

## hasRowSecurity flag

```c
bool *hasRowSecurity;
```

Set true if any RLS quals were added. Bubbles up to the Query's
`hasRowSecurity` flag, then to `PlannerInfo.glob->hasRowSecurity`,
and eventually appears in `EXPLAIN` output via the "Row
security: ..." line.

Used in plan-cache invalidation: when policies change
(`ALTER POLICY`), all cached plans with `hasRowSecurity = true`
get invalidated.

## WITH CHECK and INSERT/UPDATE

For INSERT and UPDATE, RLS has two sides:
- **USING** — which rows the user can SEE / UPDATE / DELETE.
- **WITH CHECK** — which rows the user can CREATE / NEW
  versions of.

```sql
CREATE POLICY p ON t FOR INSERT WITH CHECK (col1 = current_user);
```

The `withCheckOptions` returned from
`get_row_security_policies` enforces the WITH CHECK at write
time: tuples are written first, then the check runs; if it
fails, the row is rolled back via ereport(ERROR).

## RLS bypass — superuser + ROW LEVEL SECURITY OFF

- Superusers bypass RLS unless `BYPASSRLS` permission is
  explicitly NOT granted (configurable per role).
- Table owners bypass RLS by default; `FORCE ROW LEVEL
  SECURITY` removes the exemption.
- `SET row_security = off` causes RLS-protected queries to
  fail with an error (vs. silently returning fewer rows).

## Common review-time concerns

- **Permissive vs restrictive matters** — easy to get the
  query semantics wrong.
- **PolicyQual on subqueries** — policies on views nested in
  the query need recursive application.
- **Leaky operators bypass RLS** — `WITH (security_barrier)`
  flag prevents pushdown of leaky quals through the barrier.
- **WITH CHECK is post-write** — failed checks rollback the
  row; potentially expensive.
- **EXPLAIN exposes policies** — `EXPLAIN (VERBOSE)` lists
  applied policies for debugging.
- **Plan-cache invalidation on policy change** — ALTER POLICY
  drops all dependent plans.

## Invariants

- **[INV-1]** Policies retrieved at rewrite time, applied as
  RTE securityQuals.
- **[INV-2]** PERMISSIVE OR'd; RESTRICTIVE AND'd on top.
- **[INV-3]** Quals make the RTE behave as a
  security-barrier.
- **[INV-4]** WITH CHECK runs post-write; failure → ERROR.
- **[INV-5]** Superuser / table-owner bypass per role
  configuration.

## Useful greps

- The entry point:
  `grep -n 'get_row_security_policies\|add_security_quals' source/src/backend/rewrite/rowsecurity.c | head -10`
- Policy lookup in pg_policy:
  `grep -RIn 'GetSecurityPoliciesForRelation\|pg_policy' source/src/backend/rewrite | head -10`
- securityQuals consumers:
  `grep -RIn 'securityQuals' source/src/backend | head -15`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/rewrite/rowsecurity.c`](../files/src/backend/rewrite/rowsecurity.c.md) | 98 | get_row_security_policies entry |
| [`src/backend/rewrite/rowsecurity.c`](../files/src/backend/rewrite/rowsecurity.c.md) | 715 | add_security_quals injection |
| [`src/backend/rewrite/rowsecurity.c`](../files/src/backend/rewrite/rowsecurity.c.md) | — | + helpers |
| [`src/include/catalog/pg_policy.h`](../files/src/include/catalog/pg_policy.h.md) | — | catalog schema |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/view-pushdown-via-rewriter.md` —
  companion (similar quals-injection).
- `knowledge/idioms/security-barrier-views.md` — companion
  (RLS sets security_barrier).
- `knowledge/idioms/cached-plan-invalidation.md` — ALTER
  POLICY invalidates plans.
- `knowledge/data-structures/restrictinfo.md` — RestrictInfo
  with `security_level` records pushdown level.
- `knowledge/subsystems/parser-and-rewrite.md` — rewriter.
- `.claude/skills/executor-and-planner/SKILL.md` —
  companion.
- `source/src/backend/rewrite/rowsecurity.c` — entry +
  helpers.
- `source/src/include/catalog/pg_policy.h` — catalog schema.
