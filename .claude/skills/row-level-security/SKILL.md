---
name: row-level-security
description: PostgreSQL's Row-Level Security (RLS) — `CREATE POLICY` / `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` / policy application in the rewriter — plus the related security-barrier machinery + leakproof qualification checks. Loads when the user asks about RLS policy semantics (USING vs WITH CHECK, PERMISSIVE vs RESTRICTIVE), how policies are applied to a query at rewrite time, why a qual can/cannot be pushed below a security barrier, the leakproof function attribute, ROLE mapping for BYPASSRLS / NOFORCERLS, `row_security` GUC, or debugging why an RLS policy is/isn't firing. Also covers security-barrier views (`WITH (security_barrier = true)`), which use the same qual-pushdown-prohibition machinery. Skip when the ask is about pg_hba.conf-level authentication, GRANT/REVOKE table-level privileges, SELinux (`sepgsql`), or database-level security features unrelated to per-row visibility.
when_to_load: Design or debug RLS policies; extend the rewriter's policy-application logic; understand why the planner isn't pushing a qual through a security barrier; add / audit `leakproof`-required code paths; work with security-barrier views.
companion_skills:
  - executor-and-planner
  - catalog-conventions
  - error-handling
---

# row-level-security — RLS policies + security barriers + leakproof

Row-Level Security lets a table's owner attach `POLICY` rules that filter which rows a user can SELECT/UPDATE/DELETE. The rules are applied at **rewrite time** (before the planner runs), so RLS-filtered rows never even reach the executor. But that only works if the planner can't accidentally leak filtered-out row content by pushing untrusted qualifications below the RLS filter — hence the **security-barrier** infrastructure and the **leakproof** function attribute.

Three interlocking mechanisms:

1. **Policies** (`commands/policy.c` + `rewrite/rowsecurity.c`) — the catalog + rewriter side.
2. **Security-barrier views** (`WITH (security_barrier = true)`, in `rewrite/rewriteHandler.c` + planner) — same qual-pushdown-prohibition applied to a view.
3. **Leakproof functions** — an attribute on `pg_proc` rows that lets the planner push a qual through a security barrier if the function can't leak information via error messages or timing.

## The file map

| File | KB | Role |
|---|---:|---|
| `commands/policy.c` | 35 | The `CREATE POLICY` / `ALTER POLICY` / `DROP POLICY` DDL implementation. Manages `pg_policy` catalog rows. |
| `rewrite/rowsecurity.c` | 30 | Rewriter integration. `get_row_security_policies` builds the USING + WITH CHECK quals to inject into the query. Called from `rewriteHandler.c` for every RTE. |
| `utils/misc/rls.c` | 5 | Helpers: `check_role_for_policy`, `row_security` GUC handling. |
| `catalog/pg_policy.h` + `.dat` | — | Catalog definition. Each policy is one row per (relation, policyname). |

Also:

- `include/rewrite/rowsecurity.h` — the public API surface.
- `catalog/heap.c` — `heap_create_with_catalog` handles the `rowsecurity` bit on relation creation.

## The policy application flow

```
[user runs] SELECT * FROM t WHERE some_condition(x)
    ↓
parser produces Query with RTE for `t`
    ↓
rewriter: for each RTE, get_row_security_policies(t, cmd, role):
    - fetch pg_policy rows matching (relation=t, role covered)
    - split into permissive vs restrictive
    - build one big USING qual (permissive: OR'd; restrictive: AND'd)
    - build one big WITH CHECK qual for INSERT/UPDATE
    - mark the RTE with `securityQuals = <USING quals>` and
      `securityRLSApplied = true`
    ↓
planner sees `securityQuals` on the RTE:
    - treats it like a security-barrier subquery
    - refuses to push qual `some_condition(x)` INSIDE `securityQuals`
      unless `some_condition` is leakproof
    ↓
executor runs: RLS-filtered rows never enter the plan tree
```

## USING vs WITH CHECK

- **USING** — visibility qual. Rows failing this qual are INVISIBLE to SELECT/UPDATE/DELETE.
- **WITH CHECK** — write qual. INSERTs and UPDATEs that would produce a row failing this qual are REJECTED with a policy-violation error.

Common patterns:

```sql
CREATE POLICY p_read ON t
  FOR SELECT USING (owner = current_user);

CREATE POLICY p_write ON t
  FOR INSERT WITH CHECK (owner = current_user);

CREATE POLICY p_update ON t
  FOR UPDATE
  USING (owner = current_user)     -- can only update MY rows
  WITH CHECK (owner = current_user); -- can't reassign to someone else
```

## PERMISSIVE vs RESTRICTIVE

- **PERMISSIVE** (default) — multiple policies OR'd together. Any permissive policy that passes → row is visible.
- **RESTRICTIVE** — AND'd together AND with the permissive union. Must pass ALL restrictive policies AND at least one permissive.

Effective qual = `(perm_1 OR perm_2 OR ...) AND rest_1 AND rest_2 AND ...`.

If no permissive policies exist but restrictive ones do, ALL rows are filtered out (empty permissive union). Common footgun: adding a restrictive policy without a permissive one hides everything.

## Role coverage

Each policy names 0+ roles (`TO role1, role2, ...`); default `PUBLIC`. A user matches a policy if:
- The policy's role list is empty (PUBLIC), OR
- The user is a member (direct or via role inheritance) of any listed role.

Special role attributes:

- `BYPASSRLS` — user attribute (`ALTER USER u BYPASSRLS`). Skips RLS entirely on all tables. Reserved for admins / replication users.
- `NOFORCERLS` (`ALTER TABLE t FORCE ROW LEVEL SECURITY`) — forces RLS to apply EVEN to the table owner. Without FORCE, table owner bypasses RLS on their own tables (a common surprise).

## The `leakproof` mechanism

The planner cannot push a non-leakproof qual below a security barrier — doing so would let the qual observe rows that RLS filters out (via slow timing, error messages, etc.).

A function is `leakproof` if it CANNOT leak information about its arguments via anything other than its return value. Marking a function leakproof is a **security assertion** by the author; getting it wrong is a subtle vulnerability.

Examples:

- `int4eq(int, int)` — leakproof. Two ints compared; deterministic; no error path that reveals values.
- `int4div(int, int)` — NOT leakproof. Divide-by-zero errors reveal the divisor.
- `like(text, text)` — arguable; historically NOT leakproof due to error paths in the pattern parser. Some LIKE variants are marked leakproof in modern PG.

Managing leakproof marks:

- `CREATE FUNCTION ... LEAKPROOF` requires superuser.
- View leakproof status: `SELECT proname, proleakproof FROM pg_proc`.
- Effect on RLS-affected queries: EXPLAIN shows quals separated into "Filter" (post-RLS) vs "Index Cond" / "Recheck Cond" — non-leakproof quals stay as Filter above the RLS scan.

## Security-barrier views

`CREATE VIEW v WITH (security_barrier = true) AS SELECT ...` uses the SAME machinery as RLS. The view's underlying rels are wrapped in a subquery-shaped RTE that gets the `securityQuals` treatment. A user's WHERE quals against the view can't be pushed inside the view definition unless leakproof.

This is why `security_barrier` views are the recommended pattern for column-level security via views — they prevent qual leakage that would otherwise let an attacker observe hidden columns via slow-qual timing.

## Common patch shapes

### Add a new policy-related feature

- Extend `pg_policy` catalog if the feature adds a new attribute.
- Update `commands/policy.c` for DDL parsing + validation.
- Update `rewrite/rowsecurity.c`'s `get_row_security_policies` if application semantics change.
- Add regression tests in `src/test/regress/sql/rowsecurity.sql`.

### Mark a function leakproof (retroactively)

- Verify by code review that EVERY error path the function can take doesn't reveal argument values.
- Verify no side-effect (writes, logging) reveals arguments.
- Update `pg_proc.dat` entry: `proleakproof => 't'`.
- Bump `CATALOG_VERSION_NO`.
- Note: security-sensitive. Historically these changes need multiple committer review.

### Add a new security-barrier-like RTE mark

Very rare. Would touch `parsenodes.h` (`RangeTblEntry.securityQuals`) + planner qual-pushdown logic in `optimizer/util/clauses.c` (contain_leaked_vars, etc.) + `optimizer/path/allpaths.c` (subquery-plan generation).

### Debug "my RLS policy isn't working"

- Check `SET row_security = on` — off disables RLS enforcement (only allowed for BYPASSRLS or superuser).
- Check role coverage: is the current role in the policy's `TO ...` list?
- Check FORCE ROW LEVEL SECURITY: is the table owner running the query? Without FORCE they bypass.
- Check EXPLAIN — is `securityQuals` reflected?
- Check for RESTRICTIVE policies without PERMISSIVE — hides everything.

## Pitfalls

- **Table owner bypass** — without `FORCE ROW LEVEL SECURITY`, the OWNER of a table can read/write everything regardless of policies. Common surprise: "my policy doesn't apply to me" — because you're the owner.
- **Empty permissive → nothing visible** — a table with only RESTRICTIVE policies (no PERMISSIVE) filters out ALL rows for non-bypass users.
- **`row_security = off`** — a superuser can set this to bypass RLS. Reserved for maintenance queries; DON'T let application code rely on this.
- **Leakproof lies** — marking a non-leakproof function as leakproof is a silent security bug. The planner will push quals through security barriers using it, potentially exposing filtered rows.
- **`pg_dump` and RLS** — by default dump runs as superuser and sees everything. If you want RLS-respecting dumps, use `pg_dump --enable-row-security` under a non-superuser.
- **Policy on partitioned tables** — policies on the PARENT apply to all children automatically (via inheritance), but policies on children DO NOT apply when accessing via the parent (surprising). Prefer parent-only policies for partitioned tables.
- **`WITH CHECK` on UPDATE also applies to the OLD row's version** — a subtle case: an UPDATE that satisfies USING but produces a new row failing WITH CHECK errors out. Not silently filtered.
- **Views and RLS interact** — a view over an RLS-enabled table gets the table's policies applied at rewrite. But the view's OWN quals are subject to the view owner's privileges (or SECURITY INVOKER caller's, in PG 17+).
- **Non-leakproof quals stay above the barrier** — you might see EXPLAIN showing your WHERE clause as a Filter node, not an Index Cond, on RLS tables. That's the qual staying outside the security barrier. Marking your function leakproof (if truly safe) fixes this.

## Related corpus

- **Idioms** (2 relevant): `row-security-policy-application` (the rewriter side), `security-barrier-views` (the qual-pushdown-prohibition machinery — shared with RLS).
- **Subsystem**: `parser-and-rewrite` (RLS is a rewriter feature); `optimizer` (leakproof qual pushdown decisions).
- **Related sessions**: `2026-06-09-a12-contrib-security.md` (contrib security audit — includes RLS bypass primitive checks).
- **Related planning**: security-sensitive planning slugs may touch RLS assumptions.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom row-security-policy-application
python3 scripts/corpus-chain.py --file src/backend/rewrite/rowsecurity.c
python3 scripts/corpus-chain.py --file src/backend/commands/policy.c
```

Surfaces the rewriter neighborhood + the DDL side.

## Boundary

**Use this skill** for RLS policies + security-barrier views + leakproof semantics.

**Don't use** for:
- **`pg_hba.conf` / authentication** — separate; connection-time role authentication.
- **`GRANT` / `REVOKE`** — separate; table-level privileges. RLS is a layer ON TOP of GRANT.
- **`sepgsql`** — contrib module doing SELinux-based MAC. Uses different hooks.
- **Column-level privileges** (`GRANT SELECT (col1, col2)`) — separate; column-list ACL.
- **Column masking via views** — that's data-hiding via view definitions; RLS is row-hiding via rewriter.
