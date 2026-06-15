---
path: src/test/modules/test_oat_hooks/test_oat_hooks.c
anchor_sha: e18b0cb7344
loc: 517
depth: read
---

# src/test/modules/test_oat_hooks/test_oat_hooks.c

## Purpose

Exercises the Object Access Type (OAT) hook family — the extension points that
external MAC providers (sepgsql, audit modules, row-level policy plugins) use
to veto DDL, DML, or namespace-search operations. Installs all four flavors of
hook (`object_access_hook`, `object_access_hook_str`,
`ExecutorCheckPerms_hook`, `ProcessUtility_hook`) and gates them on per-class
GUCs so regression queries can deny one category at a time and inspect the
resulting error/NOTICE stream. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `test_oat_hooks.c:73` | Defines ten `PGC_SUSET`/`PGC_USERSET` bool GUCs under `test_oat_hooks.*`, reserves the prefix, installs the four hooks |
| `REGRESS_object_access_hook_str` (static) | `:276` | Handles `OAT_POST_ALTER` for parameter ACL classes — distinguishes SET vs ALTER SYSTEM |
| `REGRESS_object_access_hook` (static) | `:324` | Generic object-access dispatch for `OAT_POST_CREATE` / `OAT_DROP` / `OAT_POST_ALTER` / `OAT_NAMESPACE_SEARCH` / `OAT_FUNCTION_EXECUTE` / `OAT_TRUNCATE` |
| `REGRESS_exec_check_perms` (static) | `:347` | Hooks DML permission checks |
| `REGRESS_utility_command` (static) | `:379` | Hooks utility-statement dispatch; forwards to `standard_ProcessUtility` |
| `accesstype_to_string` / `accesstype_arg_to_string` (static) | `:417`, `:457` | Decode OAT enum + ACL-bit subId into human-readable strings for NOTICE output |

## Internal landmarks

- The hook-chain pattern is followed strictly: every install records the
  previous hook into a `next_*_hook` static (`:213-226`) and every fired hook
  invokes its predecessor before returning (`:282`, `:338`, `:362`, `:402`).
- `MarkGUCPrefixReserved("test_oat_hooks")` (`:210`) keeps the
  test-only GUCs from leaking into placeholder limbo if the module is later
  unloaded.
- Audit messages skip parallel workers (`!IsParallelWorker()`, `:237`) so
  output stays deterministic under `debug_parallel_query = regress`.
- The string-ACL hook decodes a bitwise `subId` of `ACL_SET | ACL_ALTER_SYSTEM`
  separately from each bit alone (`:289-313`) so the test can confirm the
  hook fires once with both bits when the user has both privileges.

## Invariants & gotchas

- **Test module — never load in production.** It installs four global
  hooks and emits NOTICE per operation; serious overhead and noise.
- The hooks are installed at module load and there is **no removal path** —
  once `LOAD 'test_oat_hooks'` happens in a session, the per-session state
  persists for that backend's life.
- Chain-of-responsibility ordering: `next_*_hook` is invoked **after** the
  test's own check (e.g. `REGRESS_object_access_hook` `:330` ereports BEFORE
  forwarding) so deny decisions short-circuit and never reach the next hook.
- For `OAT_NAMESPACE_SEARCH` the `ns_arg->result` is examined but not mutated
  — this hook is purely advisory at the audit level.
- The "internal" subId distinction (`ObjectAccessPostCreate::is_internal`,
  `:468`) matters: internal creates (e.g. catalog rows from a CREATE TABLE)
  should not trigger user-visible denials in real MAC providers.

## Cross-refs

- `source/src/include/catalog/objectaccess.h` — `ObjectAccessType` enum and
  the `ObjectAccessPostCreate` / `ObjectAccessDrop` / `ObjectAccessPostAlter`
  / `ObjectAccessNamespaceSearch` arg structs.
- `source/src/backend/catalog/objectaccess.c` — central dispatch.
- `source/contrib/sepgsql/` — the real-world consumer of these hooks.
- `source/src/backend/tcop/utility.c` — `ProcessUtility_hook` call site.
