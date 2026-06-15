---
path: src/test/modules/test_rls_hooks/test_rls_hooks.c
anchor_sha: e18b0cb7344
loc: 164
depth: read
---

# src/test/modules/test_rls_hooks/test_rls_hooks.c

## Purpose

Demonstrates and tests the row-level-security **policy hooks**
(`row_security_policy_hook_permissive` /
`row_security_policy_hook_restrictive`) — the extension-side entry
points that let a loaded module inject extra `RowSecurityPolicy`s into
the planner's policy-collection step for specific tables. Used by the
regression suite to confirm that hook-supplied policies are merged
correctly with table-level policies. `[verified-by-code]`
`test_rls_hooks.c:32-38`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:32` | Installs both RLS hooks |
| `test_rls_hooks_permissive` | `:43` | Returns a list of one permissive policy for `rls_test_permissive` / `rls_test_both` |
| `test_rls_hooks_restrictive` | `:111` | Returns a list of one restrictive policy for `rls_test_restrictive` / `rls_test_both` |

## Internal landmarks

- Both hook functions follow the same shape:
  1. Filter by relation name; return `NIL` if not a target table.
  2. Build a `ParseState`, add the relation as an RTE with
     `AccessShareLock`, and `addNSItemToQuery`.
  3. Build a `current_user = ColumnRef("username" / "supervisor")`
     expression, run it through `transformWhereClause` with
     `EXPR_KIND_POLICY`, and `assign_expr_collations`.
  4. Copy that qual into `with_check_qual`, return a single-element list.
- Policy fields: `policy_name = "extension policy"`, `polcmd = '*'`
  (applies to all command types), `roles = {ACL_ID_PUBLIC}`.

## Invariants & gotchas

- TEST MODULE — hook install is irreversible global state once `_PG_init`
  runs `[verified-by-code]` `:36-37`.
- Restrictive policies alone visibly hide every row unless a permissive
  policy also exists. The test's `rls_test_both` table demonstrates the
  intended both-kinds-loaded pattern `[from-comment]` `:106-109`.
- Both hooks expand the **same** column references (`username` for
  permissive, `supervisor` for restrictive) — the test schema must have
  those columns or query parsing fails.
- `palloc0_object` zero-initializes the `RowSecurityPolicy`, ensuring
  `hassublinks = false` and unset fields like `polroles` remain zero
  until explicitly set.

## Cross-refs

- `knowledge/files/src/test/modules/test_rls_hooks/test_rls_hooks.h.md` —
  public declarations.
- `source/src/include/rewrite/rowsecurity.h` —
  `RowSecurityPolicy` struct + hook variable declarations.
- `source/src/backend/rewrite/rowsecurity.c` — where the hooks are
  invoked during policy collection.
