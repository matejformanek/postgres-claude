# src/test/modules/test_oat_hooks/test_oat_hooks.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 517
**Verification depth:** full read

## Role

A test/reference module exercising PostgreSQL's mandatory-access-control (MAC) surface: it installs every Object Access Type hook plus the executor permission hook and the ProcessUtility hook, then optionally logs (audit) and/or denies operations based on GUCs. [from-comment] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:4`. On `_PG_init` it chains itself onto `object_access_hook`, `object_access_hook_str`, `ExecutorCheckPerms_hook`, and `ProcessUtility_hook`, saving the previous values so the chain is preserved. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:212-226`. It is a Phase-D-relevant trust-boundary surface: it demonstrates exactly which object names, access types, and command tags become visible to a loaded extension via these hooks. [inferred]

## Public API

- `_PG_init` — module load callback: defines the GUCs, calls `MarkGUCPrefixReserved("test_oat_hooks")`, and installs all four hooks (saving the previous handlers). [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:73-227`
- `PG_MODULE_MAGIC` — marks the module as a loadable PG module. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:24`

No SQL-callable `PG_FUNCTION_INFO_V1` functions are exported; all behavior is via installed hooks. [verified-by-code] (no `PG_FUNCTION_INFO_V1` occurrences in file)

## Invariants

- INV-1: Each installed hook saves the prior handler into a `next_*` static and forwards to it (chain preservation), so co-loaded modules are not displaced. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:213-226`, forwarding at `:282-285,338-339,362-364,402-405`
- INV-2: `ProcessUtility` chaining: if `next_ProcessUtility_hook` is NULL, the module must call `standard_ProcessUtility` so command processing still happens. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:402-409`
- INV-3: Audit messages are emitted only from a leader process (`!IsParallelWorker()`), to keep results deterministic under `debug_parallel_query = regress`. [from-comment][verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:232-237`
- INV-4: Deny decisions exempt superusers — every deny test is gated on `!superuser_arg(GetUserId())`. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:292,299,306,330,355,396`
- INV-5: The audit helpers `pfree` the `action` and `objName` strings they are handed, so callers must pass freshly-allocated (e.g. `pstrdup`/`psprintf`) strings, not string literals. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:251-254`

## Notable internals

- The `object_access_hook` chain: `REGRESS_object_access_hook` handles the Oid-keyed access types (OAT_POST_CREATE, OAT_DROP, OAT_POST_ALTER, OAT_NAMESPACE_SEARCH, OAT_FUNCTION_EXECUTE, OAT_TRUNCATE), audits attempt, optionally denies via `REGRESS_deny_object_access`, forwards, then audits success. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:323-344`
- The `object_access_hook_str` chain: `REGRESS_object_access_hook_str` handles string-named objects (GUC parameter ACLs). For `OAT_POST_ALTER` on a ParameterAcl it decodes `subId` against `ACL_SET` / `ACL_ALTER_SYSTEM` bits and denies set/alter-system based on `REGRESS_deny_set_variable` / `REGRESS_deny_alter_system`; an unknown subId raises `elog(ERROR, "Unknown ParameterAclRelationId subId")`. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:275-321`
- `ExecutorCheckPerms_hook`: `REGRESS_exec_check_perms` computes `allow = !REGRESS_deny_exec_perms || am_super`, raises ERROR if `do_abort && !allow`, then ANDs in the next hook's verdict, and audits success/failure. Returns the boolean verdict. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:346-376`
- `ProcessUtility_hook`: `REGRESS_utility_command` derives the command tag via `GetCommandTagName(CreateCommandTag(pstmt->utilityStmt))`, denies all utility commands for non-superusers if `REGRESS_deny_utility_commands`, then forwards / falls back to `standard_ProcessUtility`. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:378-415`
- `accesstype_to_string` maps `ObjectAccessType` to a label and appends `subId` decoding (set / alter system / all privileges); `accesstype_arg_to_string` casts the `arg` void* to the per-access-type struct (`ObjectAccessPostCreate`, `ObjectAccessDrop`, `ObjectAccessPostAlter`, `ObjectAccessNamespaceSearch`) and renders its fields, including dropflags decoding. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:417-517`
- What it logs to NOTICE: hook name, superuser-vs-non, access type, decoded action, and the object name/arg detail — i.e. object names and namespace-search results cross the trust boundary into the hook. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:241-248,499-506`
- GUCs: six deny/audit booleans plus `user_var{1,2}` (PGC_USERSET) and `super_var{1,2}` (PGC_SUSET) dummy variables used to test privilege behavior on USERSET vs SUSET variables. [verified-by-code] `source/src/test/modules/test_oat_hooks/test_oat_hooks.c:79-208`

## Cross-refs

- `source/src/include/catalog/objectaccess.h` — `ObjectAccessType` enum, the `object_access_hook` / `object_access_hook_str` declarations, and the `ObjectAccessPostCreate` / `ObjectAccessDrop` / `ObjectAccessPostAlter` / `ObjectAccessNamespaceSearch` arg structs.
- `source/src/backend/catalog/objectaccess.c` — `RunObjectPostCreateHook` / `RunNamespaceSearchHook` etc. invokers that call these hooks.
- `source/src/include/executor/executor.h` — `ExecutorCheckPerms_hook_type` and `ExecCheckPermissions`.
- `source/src/include/tcop/utility.h` — `ProcessUtility_hook_type` and `standard_ProcessUtility`.
- `source/src/include/utils/acl.h` — `ACL_SET` / `ACL_ALTER_SYSTEM` bit definitions.
- `source/src/test/modules/test_oat_hooks/` — `.sql`/`.out` expected-output files that pin the audit message format.

## Potential issues

- **[ISSUE-question: deny path runs after side effects for POST hooks]** `src/test/modules/test_oat_hooks/test_oat_hooks.c:289-313` — denies on `OAT_POST_ALTER` and `OAT_POST_CREATE`-class events fire in the *post* hook, i.e. after the catalog mutation already happened; the ereport(ERROR) relies on transaction rollback to undo it. This is correct for a MAC test module but is a documented limitation of POST_* hooks as an enforcement point, worth noting for any Phase-D trust-boundary analysis. Severity: nit.
- **[ISSUE-question: audit emission gated only on leader, not on a re-entrancy guard]** `src/test/modules/test_oat_hooks/test_oat_hooks.c:237` — comment explains the `!IsParallelWorker()` guard exists solely for deterministic output under `debug_parallel_query`; no functional concern, but it means worker-side accesses are silently un-audited. Documented intent, not a bug. Severity: nit.
