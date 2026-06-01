# rowsecurity.c

- **Source:** `source/src/backend/rewrite/rowsecurity.c` (947 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Row-Level Security (RLS) integration with the rewriter. Given an RTE, look
up the applicable `pg_policy` rows for the current user/role, command
type, and PERMISSIVE/RESTRICTIVE flag, and produce the qual + with-check
expressions to splice into the Query. [from-comment] `:1-21`

Default-deny semantics: when RLS is enabled on a table that has zero
policies (or zero policies matching the current command), the result is
a `false`-qual — no rows visible / no rows modifiable. [from-comment]
`:7-10`

## Public entry

`get_row_security_policies(root, rte, rt_index, &securityQuals,
&withCheckOptions, &hasRowSecurity, &hasSubLinks)` — called by
`fireRIRrules` (`rewriteHandler.c:2256-…`) per RTE in the rangetable. The
returned quals are *prepended* to whatever security quals already exist on
the RTE (e.g. from view-update permissions), then the rewriter walks them
to detect contained sublinks (which need RIR processing too).

## PERMISSIVE vs RESTRICTIVE composition

- Multiple PERMISSIVE policies are combined with **OR**.
- Each RESTRICTIVE policy is combined with **AND**.
- Final shape: `(perm1 OR perm2 OR ...) AND restr1 AND restr2 AND ...`.
- If no PERMISSIVE policy matches: the OR-list collapses to `false` →
  default-deny.

## WithCheckOptions

For INSERT/UPDATE, RLS produces *additional* check expressions that the
executor verifies *after* the row is computed (post-trigger). The
`WCO_RLS_INSERT_CHECK` / `WCO_RLS_UPDATE_CHECK` /
`WCO_RLS_CONFLICT_CHECK` kinds are emitted here.

## Bypass

`row_security` GUC + `BYPASSRLS` role attribute + table ownership can
each disable RLS. The bypass decisions are computed here and short-circuit
the policy-fetch path.

## RLS + views: `adjust_view_column_set`

Referenced from `rewriteHandler.c:99`. When an RLS policy on a table
flows up through a view, the column-set in the policy's check has to be
remapped through the view's targetlist. This helper does the bitmap remap.

## Caveats / sharp edges

- "Last in the rewrite pipeline" property is critical: RLS quals can
  contain sublinks which themselves reference views; if RLS ran before
  view expansion, sublinks would get expanded twice (once during the
  per-RTE loop, once during sublink recursion in `fireRIRrules`). The
  ordering at `rewriteHandler.c:2249-2255` is what avoids this.
- Result-relation RLS quals are *not* visible to FOR UPDATE locking
  semantics directly — they're enforced at the executor's `EvalPlanQual`
  re-check after the row was already locked.
- INSERT WITH CHECK is enforced AFTER BEFORE INSERT triggers fire, so a
  trigger that mutates the row may flip whether the policy admits it.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
