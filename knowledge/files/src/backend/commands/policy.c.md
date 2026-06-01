# policy.c

- **Source path:** `source/src/backend/commands/policy.c`
- **Lines:** 1279
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Commands for manipulating policies." [from-comment, policy.c:3-4] CREATE/ALTER/DROP POLICY plus `ALTER TABLE … ENABLE/DISABLE ROW LEVEL SECURITY`. The runtime side (rewriting queries to add USING/WITH CHECK quals) lives in `rewrite/rowsecurity.c`.

## Public surface

- `CreatePolicy`, `AlterPolicy` — pg_policy DDL. Parse USING / WITH CHECK clauses (these are arbitrary boolean expressions); resolve role list (`PUBLIC` → 0; otherwise named role OIDs).
- `RemovePolicyById`, `RemoveRoleFromObjectPolicy` — DROP plus DROP ROLE cascade.
- `RelationBuildRowSecurity` — called from relcache; loads all policies for a relation into the Relation's `rd_rsdesc` so the rewriter can apply them per query.

## USING vs WITH CHECK

USING = visibility filter (which existing rows can I read/update/delete?). WITH CHECK = constraint on inserted/updated rows (does the new row pass the policy?). For UPDATE, both apply — USING gates "may I touch this row" and WITH CHECK gates "may the new version exist". For INSERT, only WITH CHECK; if WITH CHECK absent, USING is used.

## RESTRICTIVE vs PERMISSIVE

Default is PERMISSIVE (policies OR-combined). RESTRICTIVE policies AND-combine on top. The final visible-row predicate is: `(OR of all PERMISSIVE USINGs) AND (AND of all RESTRICTIVE USINGs)`.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
