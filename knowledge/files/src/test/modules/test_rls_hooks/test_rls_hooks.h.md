---
path: src/test/modules/test_rls_hooks/test_rls_hooks.h
anchor_sha: e18b0cb7344
loc: 25
depth: read
---

# src/test/modules/test_rls_hooks/test_rls_hooks.h

## Purpose

Public declarations for the `test_rls_hooks` module — the two hook
implementations that get wired into `row_security_policy_hook_permissive`
and `row_security_policy_hook_restrictive` at `_PG_init` time. The
signatures match the hook function type: `(CmdType, Relation) -> List *`
of `RowSecurityPolicy *`. `[verified-by-code]` `test_rls_hooks.h:20-23`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_rls_hooks_permissive` | `:20` | Returns permissive policies based on CmdType + Relation |
| `test_rls_hooks_restrictive` | `:23` | Returns restrictive policies based on CmdType + Relation |

## Internal landmarks

Header is purely declarative; pulls in `rewrite/rowsecurity.h` for the
`RowSecurityPolicy` and `CmdType` types.

## Invariants & gotchas

- TEST MODULE — these are demonstration hooks; loading the module installs
  RLS policies that constrain visible rows for the test schema.

## Cross-refs

- `knowledge/files/src/test/modules/test_rls_hooks/test_rls_hooks.c.md` —
  the implementation behind these declarations.
- `source/src/include/rewrite/rowsecurity.h` — hook variable declarations
  and the `RowSecurityPolicy` struct.
