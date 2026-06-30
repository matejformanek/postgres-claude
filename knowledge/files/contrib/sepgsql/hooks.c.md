# hooks.c

## One-line summary

`_PG_init` activation site plus the three central dispatchers that bridge PG's
generic hook surface (`object_access_hook`, `ExecutorCheckPerms_hook`,
`ProcessUtility_hook`) into sepgsql's per-class permission routines.

## Public API / entry points

- `_PG_init(void)` — `source/contrib/sepgsql/hooks.c:402-486`. The single load
  callback; refuses to run when `IsUnderPostmaster` is true
  (`hooks.c:409-412`). Installs GUCs `sepgsql.permissive` (PGC_SIGHUP) and
  `sepgsql.debug_audit` (PGC_USERSET) — `hooks.c:431-458`. Marks the
  `sepgsql.*` GUC namespace reserved (`hooks.c:460`). Calls
  `sepgsql_avc_init` and `sepgsql_init_client_label`, registers the
  `SEPGSQL_LABEL_TAG = "selinux"` provider hook via
  `register_label_provider` (`hooks.c:469-470`). [verified-by-code]
- `sepgsql_get_permissive(void) → bool` — `hooks.c:65-69`. Returns the cached
  GUC value.
- `sepgsql_get_debug_audit(void) → bool` — `hooks.c:76-80`.
- Static dispatchers (not in header; installed by `_PG_init`):
  - `sepgsql_object_access` (the `object_access_hook` body) —
    `hooks.c:88-285`; installed at `hooks.c:473-474`.
  - `sepgsql_exec_check_perms` (the `ExecutorCheckPerms_hook` body) —
    `hooks.c:292-307`; installed at `hooks.c:477-478`.
  - `sepgsql_utility_command` (the `ProcessUtility_hook` body) —
    `hooks.c:315-397`; installed at `hooks.c:481-482`.

## Key invariants

- The module *requires* postmaster-time load. Loading via `LOAD` or
  `shared_preload_libraries`-after-start is rejected with
  `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` (`hooks.c:409-412`).
  [verified-by-code]
- All three hooks chain to the previously-installed handlers: the original
  pointers are saved into `next_object_access_hook`,
  `next_exec_check_perms_hook`, `next_ProcessUtility_hook`
  (`hooks.c:40-42`). The chain is preserved when sepgsql is stacked behind
  another security provider. [verified-by-code]
- `sepgsql_context_info` (a `cmdtype` + an optional `createdb_dtemplate`
  string) is saved/restored across a `PG_TRY/PG_FINALLY` around the inner
  `standard_ProcessUtility` call (`hooks.c:329-396`), making the contextual
  data nest-safe across utility recursion (subcommands).
  [verified-by-code]
- `LOAD` is unconditionally rejected when `sepgsql_getenforce()` is true
  (`hooks.c:365-370`). In permissive/internal mode `LOAD` is allowed.
  [verified-by-code]

## Notable internals

The `sepgsql_object_access` dispatcher demultiplexes
`(ObjectAccessType, classId, subId)` to per-class entry points:

| access type | classId | subId | dispatched call | cite |
|-------------|---------|-------|------------------|------|
| OAT_POST_CREATE | DatabaseRelationId | 0 | `sepgsql_database_post_create(objectId, createdb_dtemplate)` | `hooks.c:109-113` |
| OAT_POST_CREATE | NamespaceRelationId | 0 | `sepgsql_schema_post_create(objectId)` | `hooks.c:115-118` |
| OAT_POST_CREATE | RelationRelationId | 0 | `sepgsql_relation_post_create(objectId)` (gated on `!is_internal`) | `hooks.c:120-136` |
| OAT_POST_CREATE | RelationRelationId | >0 | `sepgsql_attribute_post_create(objectId, subId)` | `hooks.c:137-139` |
| OAT_POST_CREATE | ProcedureRelationId | 0 | `sepgsql_proc_post_create(objectId)` | `hooks.c:141-144` |
| OAT_DROP | (same matrix, gated on `!(PERFORM_DELETION_INTERNAL)`) | | per-class drop routines | `hooks.c:153-190` |
| OAT_TRUNCATE | RelationRelationId | | `sepgsql_relation_truncate(objectId)` | `hooks.c:193-205` |
| OAT_POST_ALTER | (same matrix, gated on `!is_internal` for rel) | | per-class `*_setattr` routines | `hooks.c:207-253` |
| OAT_NAMESPACE_SEARCH | NamespaceRelationId | | `sepgsql_schema_search(objectId, ns_arg->ereport_on_violation)`; stacks with previous result via short-circuit on `!ns_arg->result` | `hooks.c:255-272` |
| OAT_FUNCTION_EXECUTE | ProcedureRelationId | | `sepgsql_proc_execute(objectId)` | `hooks.c:274-279` |
| default | | | `elog(ERROR, "unexpected object access type")` | `hooks.c:281-283` |

The "should I check or not" gate is the `is_internal` /
`PERFORM_DELETION_INTERNAL` predicate, applied per-branch:

- `OAT_POST_CREATE` on `RelationRelationId` with subId == 0 skips iff
  `is_internal` is true (`hooks.c:132-133`). Comment explains: TOAST tables,
  index rebuilds, and ALTER TABLE's internal rebuilds don't get labels and
  don't get checked.
- `OAT_POST_CREATE` on Database/Namespace/Procedure asserts `!is_internal`
  unconditionally — internal creation of those classes is not expected.
- `OAT_DROP` skips when `drop_arg->dropflags & PERFORM_DELETION_INTERNAL`
  (`hooks.c:162-163`) — temp-object cleanup at session end is silent.
- `OAT_POST_ALTER` on relations gates on `is_internal`
  (`hooks.c:234-235`); on database/schema/proc it asserts `!is_internal`.

The DML hook (`sepgsql_exec_check_perms`) is a thin wrapper: it calls the
previous hook first; on a `false` from that hook, returns false immediately
("if any provider denies, we don't need to check") and otherwise delegates to
`sepgsql_dml_privileges` (`hooks.c:292-307`).

The utility hook only acts on two NodeTag cases:

- `T_CreatedbStmt` (`hooks.c:340-357`) — scans the option list for `template`
  and saves the value into `sepgsql_context_info.createdb_dtemplate` so the
  later `OAT_POST_CREATE` callback can pass it to
  `sepgsql_database_post_create` (where it is used to look up the source
  DB's label). [verified-by-code]
- `T_LoadStmt` (`hooks.c:359-371`) — outright `ereport(ERROR, ...)` when
  enforcing. The comment is explicit: "a binary module can arbitrarily
  override hooks." This is the LOAD-blocking design.

## Trust boundary / Phase D surface

This file is the *entire activation surface* of sepgsql.

- **`shared_preload_libraries = sepgsql` is the only activation path.**
  `_PG_init` rejects `IsUnderPostmaster` invocations
  (`hooks.c:409-412`). Therefore a runtime `LOAD 'sepgsql'` after postmaster
  start cannot enable MAC. **Conversely**, removing the module from
  `shared_preload_libraries` and restarting the cluster silently disables
  *all* MAC. There is no `pg_seclabel`-side residue that would refuse
  operation in an unloaded cluster — labels just become inert text. **This is
  the canonical "silent MAC removal" Phase D risk.**
  [ISSUE-defense-in-depth: removing sepgsql from shared_preload_libraries
  silently loses MAC enforcement while leaving labels on disk; nothing flags
  this on next startup (confirmed)]

- **DAC vs MAC ordering.** `ExecutorCheckPerms_hook` fires *after* PG's
  ACL check in `ExecCheckPermissions` (executor/execMain.c). sepgsql is a
  veto-only layer: PG-ACL must allow first; MAC can then deny. The
  reciprocal path — PG-ACL denies but MAC allows — never happens because
  the executor short-circuits.

- **`sepgsql.permissive` is `PGC_SIGHUP`** (`hooks.c:436`). Live-changed only
  by a reload from a privileged client (superuser-write of postgresql.conf
  or `pg_reload_conf()`). A normal user cannot per-session disable
  enforcement. *However*, the effective enforcement is also keyed on
  `sepgsql_getenforce()` which combines `sepgsql_mode == DEFAULT` and
  `selinux_status_getenforce() > 0` (`selinux.c:651-657`). The OS-level
  setenforce(0) by root flips the whole cluster permissive without DB
  reload. [verified-by-code]

- **`sepgsql.debug_audit` is `PGC_USERSET`** (`hooks.c:454`). A user can flip
  this. The variable controls only the audit *volume* (auditing all
  decisions rather than respecting `auditallow/auditdeny`) — it does not
  affect enforcement. Still, an attacker can make the audit log a lot
  louder or quieter for their session. [ISSUE-audit-gap:
  sepgsql.debug_audit is PGC_USERSET — user-controlled audit logging volume
  for own session (maybe)]

- **`_PG_init` calls `is_selinux_enabled()`**, and if 0 sets mode DISABLED
  and *returns without installing any hook* (`hooks.c:419-423`). On a host
  without SELinux loaded, sepgsql is a no-op even when in
  `shared_preload_libraries`. No log message warns of this beyond what
  libselinux itself emits. [ISSUE-defense-in-depth: silent fall-through to
  DISABLED when host SELinux is not loaded — DBA may believe sepgsql is
  enforcing when it isn't (likely)]

- **`object_access_hook` is *single-pointer*, not a chain.** sepgsql saves
  the previous pointer to `next_object_access_hook` and calls it first
  (`hooks.c:95-96`). A later-loaded extension that *also* installs an
  `object_access_hook` without preserving the chain would silently overwrite
  sepgsql's installation — sepgsql would still be linked via
  `next_object_access_hook` but inaccessible. Same risk for
  `ExecutorCheckPerms_hook` (`hooks.c:477`) and `ProcessUtility_hook`
  (`hooks.c:481`). [ISSUE-defense-in-depth: chain integrity depends on every
  later-loaded extension preserving and chaining the prior hook pointer; no
  registration registry exists (likely)]

- **`LOAD` is blocked only when `sepgsql_getenforce()` is true**
  (`hooks.c:365`). In permissive / internal mode `LOAD` is allowed. An admin
  flipping the OS to permissive (setenforce 0) re-opens
  `LOAD '/some/path.so'` without an audit beyond the rmgrdesc that
  PostgreSQL emits for LOAD itself. [ISSUE-security: LOAD permitted in
  permissive mode → an attacker who can issue `setenforce 0` at OS level
  can then `LOAD` arbitrary code via DB without re-enabling enforcement
  (maybe)]

- **`OAT_NAMESPACE_SEARCH` short-circuits on prior denial**
  (`hooks.c:262-265`). If a stacked provider already set `result = false`,
  sepgsql does *not* run its check. Correct behavior, but means sepgsql's
  audit record is suppressed when a stacked provider denies first — partial
  audit story.

- **Mis-routed type tag risk.** The dispatcher uses raw `classId` OID
  comparison. If a future catalog grows a new RelationKind without sepgsql
  noticing, the `default:` branch silently skips
  (`hooks.c:146-149, 186-189, 200-203, 248-251`). New object classes are
  *unmonitored by default* — every new catalog object class requires a
  matching sepgsql patch. [ISSUE-audit-gap: new object classes are
  unmonitored until sepgsql adds an explicit case in the dispatcher; this
  is a fail-open posture for unknown classes (confirmed)]

- **TOAST relations bypass.** `RELKIND_INDEX in pg_toast` namespace is
  skipped in `sepgsql_relation_post_create` and `sepgsql_relation_drop`
  (relation.c:277-279, 437-438). Mirror skip lives in `dml.c:171-175`
  ("hardwired" forbid DML on TOAST). [verified-by-code]

- **Bootstrap mode.** No explicit `IsBootstrapProcessingMode()` check exists
  in this file. The hook is installed unconditionally inside `_PG_init`,
  but `_PG_init` itself runs at postmaster start before bootstrap finishes;
  if running under `initdb`, sepgsql will gate operations. The flow relies
  on `is_selinux_enabled()` being 0 in initdb environments (typical) so the
  hook is never installed. [inferred]

## Cross-references

- `source/src/backend/catalog/objectaccess.c` — `InvokeObjectAccessHook*`
  helpers that drive `sepgsql_object_access`.
- `source/src/backend/executor/execMain.c` — `ExecutorCheckPerms_hook`
  invocation site (called from `ExecCheckPermissions`).
- `source/src/backend/tcop/utility.c` — `ProcessUtility_hook` invocation
  site (`ProcessUtility`).
- `source/src/backend/commands/seclabel.c` — `register_label_provider`,
  `SetSecurityLabel`, `GetSecurityLabel`; the multi-provider dispatcher
  that sepgsql plugs into via `SEPGSQL_LABEL_TAG`.
- `source/src/backend/utils/misc/guc.c` — `DefineCustomBoolVariable`,
  `MarkGUCPrefixReserved`.

<!-- issues:auto:begin -->
- [Issue register — `sepgsql`](../../../issues/sepgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-defense-in-depth: removing sepgsql from shared_preload_libraries
  silently loses MAC enforcement; on-disk labels persist as inert metadata
  (confirmed)]`
- `[ISSUE-defense-in-depth: silent fall-through to DISABLED when libselinux
  reports SELinux disabled; no LOG/WARNING is emitted from sepgsql itself
  (likely)]`
- `[ISSUE-defense-in-depth: hook chain integrity depends on every
  later-loaded extension chaining the previous pointer; no registry
  enforces this (likely)]`
- `[ISSUE-security: LOAD permitted in permissive mode (hooks.c:365); admin
  who flips setenforce 0 reopens arbitrary library loads (maybe)]`
- `[ISSUE-audit-gap: new object classes are unmonitored by default — every
  default: branch in the dispatcher is fail-open for unknown classId
  (confirmed)]`
- `[ISSUE-audit-gap: sepgsql.debug_audit is PGC_USERSET — a user can turn
  on debug audit for their session, but cannot disable normal audit; mostly
  benign (nit)]`
- `[ISSUE-correctness: PG_TRY / PG_FINALLY around standard_ProcessUtility
  saves/restores sepgsql_context_info, but only the createdb_dtemplate
  field is meaningfully nested-safe; cmdtype is overwritten on each entry
  with no synchronization beyond the save/restore (nit)]`
- `[ISSUE-documentation: hooks.c does not document that
  ProcessUtility_hook fires before parse-analyze of subcommands — the
  comment at line 376 hints at it but never names the consequence (nit)]`
- `[ISSUE-defense-in-depth: _PG_init has no explicit
  IsBootstrapProcessingMode check; relies on is_selinux_enabled() being
  zero in initdb environments (maybe)]`
- `[ISSUE-error-handling: elog(ERROR, "unexpected object access type")
  on default (hooks.c:282) — a newly-added OAT_* value would crash all
  catalog ops in a sepgsql-loaded cluster until the module is patched
  (likely)]`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-sepgsql.md](../../../subsystems/contrib-sepgsql.md)
