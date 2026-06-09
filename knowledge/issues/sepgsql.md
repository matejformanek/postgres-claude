# Issues — `contrib/sepgsql`

Per-subsystem issue register for **sepgsql**, the SELinux integration
providing label-based mandatory access control on top of PG's DAC.
**THE most security-explicit module in contrib** — every file is
about a Phase D trust-boundary mechanism. 10 source files / ~5 050
LOC.

**Parent docs:** `knowledge/files/contrib/sepgsql/*` (10 docs).

**Source:** ~53 entries surfaced 2026-06-09 by A12-3.
**Three confirmed security-class findings** worth surfacing upstream.

## Headlines

### Activation gate

`shared_preload_libraries = sepgsql` — `_PG_init`
(`hooks.c:402-486`) refuses `IsUnderPostmaster` invocations, so
runtime `LOAD` cannot enable MAC. Conversely, **removing the
module from `shared_preload_libraries` and restarting silently
disables ALL MAC while leaving labels on disk as inert metadata**.
sepgsql emits NO startup log when SELinux is disabled host-side,
so a DBA can believe sepgsql is enforcing when it is not.

### Fail-disposition

**Mostly closed**: `sepgsql_compute_avd` `ereport(ERROR)`s on
`security_compute_av_flags_raw` failure (`selinux.c:780`); `_PG_init`
FATALs on `getcon_raw` failure; `sepgsql_client_auth` FATALs on
`getpeercon_raw` (`label.c:244`). **Two fail-open caveats:**
1. Unknown object classes hit `default:` branches in the hook
   dispatcher and silently skip.
2. `sepgsql_compute_avd` falls back to `~0 allowed` when the policy
   lacks a class definition unless `security_deny_unknown() > 0`.

### `sepgsql.permissive` GUC scope

**PGC_SIGHUP (good — not USERSET).** But the **mode flip happens
only at `ClientAuthentication`** (`label.c:253-256`), so
`pg_reload_conf()` after backends are connected does NOT change
their enforcement mode — only new backends see the new value.

### THE THREE CONFIRMED SECURITY-CLASS FINDINGS

1. **Permissive-mode AVC cache widening permanently mutates
   `cache->allowed`** (`uavc.c:384`). If an admin flips PERMISSIVE
   → DEFAULT without a policy reload, **existing backends carry
   widened cache entries** until they reclaim or policy reloads.

2. **Parallel workers and other bgworkers use the SERVER's SELinux
   label as `client_label_peer`** and stay in
   `SEPGSQL_MODE_INTERNAL` — **silently non-enforcing AND
   non-auditing**. Combined with the foreign-table gap, MAC has
   real holes in modern PG workloads.

3. **`proc.c:279` typo** — ALTER FUNCTION ... SET SCHEMA does NOT
   check `add_name` on the destination namespace (re-adds to OLD
   namespace).

### Other notable findings

- **TCP connections FATAL out at ClientAuthentication** —
  effectively Unix-socket-only.
- **`sepgsql_setcon` callable by any user** — policy controls
  transition; load-bearing on policy correctness.
- **DML on foreign tables (`RELKIND_FOREIGN_TABLE`) gets NO sepgsql
  check** — confirmed gap.
- **`db_tuple` per-row MAC unimplemented** — sepgsql is column-
  level at best; row-level MAC is documented as future work but
  the class definition is there.
- **`is_internal=true` rebuilds (ALTER TABLE, REINDEX) skip
  sepgsql** — confirmed by comment.

## Cross-sweep references

- **A11 postgres_fdw cross-cluster trust boundary** + **A12 sepgsql
  parallel-worker gap** — both are "MAC/RLS attention drops when
  execution leaves the leader backend."
- **Foreign-table DML gap** (`dml.c`) + **A11 postgres_fdw NAME-
  based shippable cache** — both extend the corpus-wide NAME-vs-OID
  Phase D pattern in different directions.

## Entries (~53 total)

### sepgsql.h

- [ISSUE-correctness: `SEPG_*__*` bit positions in header are
  coupled to `selinux_catalog[].av[]` order by array index — silent
  miscompile risk if either side is reordered (likely)].
- [ISSUE-api-shape: `SEPGSQL_AVC_NOAUDIT` is a `(void *)(-1)`
  sentinel; ugly typing (nit)].
- [ISSUE-documentation: `SEPGSQL_MODE_INTERNAL` semantic not
  documented in header (nit)].

### hooks.c

- [ISSUE-defense-in-depth: removing sepgsql from
  `shared_preload_libraries` silently loses MAC; labels persist as
  inert metadata (confirmed)].
- [ISSUE-defense-in-depth: silent fall-through to DISABLED on hosts
  without SELinux; no sepgsql-side warning (likely)].
- [ISSUE-defense-in-depth: hook chain integrity depends on every
  later-loaded extension chaining the previous pointer; no registry
  (likely)].
- [ISSUE-security: `LOAD` permitted in permissive mode (`hooks.c:
  365`); `setenforce 0` reopens arbitrary library loads (maybe)].
- [ISSUE-audit-gap: new object classes are unmonitored by default —
  `default:` branches fail-open for unknown classId (confirmed)].
- [ISSUE-audit-gap: `sepgsql.debug_audit` is PGC_USERSET — user-
  controlled audit volume (nit)].
- [ISSUE-correctness: `sepgsql_context_info` save/restore only
  `createdb_dtemplate` is meaningfully nested-safe; `cmdtype`
  overwrite (nit)].
- [ISSUE-defense-in-depth: no explicit `IsBootstrapProcessingMode`
  check; relies on libselinux being disabled in initdb (maybe)].
- [ISSUE-error-handling: `elog(ERROR, "unexpected object access
  type")` on new `OAT_*` would crash all catalog ops (likely)].

### selinux.c

- [ISSUE-security: unknown-class fallback is fail-open unless
  `security_deny_unknown() > 0` (maybe)].
- [ISSUE-defense-in-depth: `sepgsql.permissive` GUC reload does not
  affect existing backends — mode flip only at `_PG_init` and
  `client_auth` (likely)].
- [ISSUE-audit-gap: audit emitted at LOG level; `log_min_messages
  > LOG` silently drops audit records (confirmed)].
- [ISSUE-error-handling: `ERRCODE_INTERNAL_ERROR` for SELinux call
  failures blends policy bugs with denials in SQLSTATE (nit)].
- [ISSUE-correctness: `selinux_catalog[X].av[i]` must satisfy
  `av_code == (1 << i)` for audit text; no Assert (nit)].
- [ISSUE-api-shape: `sepgsql_set_mode` externally linkable with no
  caller-class guard (nit)].
- [ISSUE-defense-in-depth: `SEPGSQL_MODE_INTERNAL` silently
  non-enforcing AND non-auditing; bgworkers run unmonitored
  (maybe)].
- [ISSUE-error-handling: no retry on transient libselinux failures
  from `security_compute_av_flags_raw` (nit)].

### uavc.c

- [ISSUE-security: permissive-mode cache widening (`uavc.c:384`)
  persists across mode flip from PERMISSIVE→DEFAULT in long-lived
  backends until cache reclaim or policy reload (likely)].
- [ISSUE-security: parallel workers initialize `client_label_peer`
  to server context, not originating client's label; DML checks in
  workers use wrong subject (likely)].
- [ISSUE-audit-gap: `SEPGSQL_MODE_INTERNAL` silently disables audit
  emission (confirmed)].
- [ISSUE-audit-gap: `SEPGSQL_AVC_NOAUDIT` sentinel suppresses audit
  unconditionally; pattern is fragile (nit)].
- [ISSUE-concurrency: avc_reclaim second-chance LRU is O(slots*
  entries) worst case (nit)].
- [ISSUE-memory: cache grows to threshold per backend; unique (s,t)
  fingerprint signal (nit)].
- [ISSUE-correctness: `sepgsql_avc_check_valid` retry loop could
  theoretically spin under reload storm (unverified)].
- [ISSUE-defense-in-depth: no admin "purge cache" SQL function
  (nit)].
- [ISSUE-documentation: three concepts named "permissive" — GUC,
  AVC cache field, `sepgsql_getenforce` (likely)].

### label.c

- [ISSUE-defense-in-depth: TCP connections FATAL out at
  ClientAuthentication; sepgsql effectively Unix-socket-only
  (confirmed)].
- [ISSUE-memory: `client_label_peer` from getcon/getpeercon never
  `freecon`'d per backend (nit)].
- [ISSUE-correctness: invalid stored labels silently degrade to
  "unlabeled" (likely)].
- [ISSUE-security: `sepgsql_setcon` callable by any user — policy
  controls transition; load-bearing on policy correctness
  (confirmed)].
- [ISSUE-security: bgworkers/parallel workers run with server label
  as `client_label_peer`, mode stays INTERNAL, silently
  non-enforcing and non-auditing (confirmed)].
- [ISSUE-audit-gap: `sepgsql_setcon` emits no dedicated audit
  record beyond setcurrent/dyntransition checks (nit)].
- [ISSUE-correctness: `sepgsql_subxact_callback` handles ABORT
  only, not COMMIT — pending-labels promotion via outer xact (nit)].
- [ISSUE-defense-in-depth: `sepgsql_restorecon` is the only
  initial-label bootstrap; if never run after initdb, all objects
  effectively "unlabeled" (likely)].
- [ISSUE-error-handling: `getcon_raw` failure in `_PG_init` aborts
  postmaster (nit)].
- [ISSUE-audit-gap: no dedicated audit category for label changes
  (nit)].
- [ISSUE-defense-in-depth: backend SIGTERM mid-trusted-procedure
  leaks global `client_label_func` (nit)].
- [ISSUE-api-shape: pending label list does not record subid for
  client visibility (nit)].

### database.c

- [ISSUE-audit-gap: `get_database_oid` raises before sepgsql checks
  visibility — leaks template DB existence (nit)].
- [ISSUE-correctness: nested CREATE DATABASE via SPI without
  explicit template defaults to "template1" (maybe)].
- [ISSUE-documentation: long-standing stale XXX comment about
  libselinux object name support (nit)].

### schema.c

- [ISSUE-defense-in-depth: `pg_temp` schemas all share canonical-
  name label compute; policies must explicitly handle pg_temp
  (maybe)].
- [ISSUE-audit-gap: `OAT_NAMESPACE_SEARCH` denial with
  `ereport_on_violation=false` produces no `ereport` — only AVC
  audit; lost if filtered (likely)].

### relation.c

- [ISSUE-correctness: `relation.c:197` passes
  `SEPG_DB_PROCEDURE__RELABELTO` into a `db_column` relabelto
  check; works only via bit aliasing (confirmed)].
- [ISSUE-audit-gap: foreign tables have columns but no per-column
  sepgsql labels (likely)].
- [ISSUE-defense-in-depth: partitions inherit from schema label not
  partitioned-table label; cross-partition consistency is policy-
  burden (likely)].
- [ISSUE-audit-gap: unknown relkinds silently `goto out`/return
  without check or audit (confirmed)].
- [ISSUE-memory: per-column `getObjectIdentity` churn for wide
  tables (nit)].
- [ISSUE-correctness: `SEPG_DB_TABLE__DROP` reused for sequence/
  view drop via bit aliasing (nit)].
- [ISSUE-correctness: TOAST index skip relies on
  `PG_TOAST_NAMESPACE` convention (nit)].
- [ISSUE-audit-gap: `is_internal=true` rebuilds (ALTER TABLE,
  REINDEX) skip sepgsql (confirmed by comment)].
- [ISSUE-documentation: `db_tuple` class defined but unused — XXX
  comment is years old (nit)].
- [ISSUE-correctness: `sepgsql_relation_setattr` resource cleanup
  not in `PG_TRY` (nit)].
- [ISSUE-correctness: attribute-post-create only fires on ALTER
  TABLE ADD COLUMN; CREATE TABLE columns labeled in
  `sepgsql_relation_post_create` — two paths must stay in sync
  (likely)].

### proc.c

- [ISSUE-security: `proc.c:279` typo — namespace-change setattr
  re-adds to *old* namespace instead of new; ALTER FUNCTION SET
  SCHEMA does not check `add_name` on destination (confirmed)].
- [ISSUE-audit-gap: `db_language:{implement}` defined but never
  checked (confirmed)].
- [ISSUE-correctness: `Assert(!is_internal)` skipped in release
  builds — internal proc creation silently labeled (nit)].
- [ISSUE-defense-in-depth: aggregates/operators ride pg_proc
  handling; sepgsql cannot distinguish (nit)].
- [ISSUE-audit-gap: every function call hits
  `sepgsql_proc_execute`; AVC cache hit rate critical (nit)].

### dml.c

- [ISSUE-defense-in-depth: hardwired catalog/TOAST DML denial gated
  on `sepgsql_getenforce() > 0` — permissive mode loses protection
  (likely)].
- [ISSUE-security: DML on foreign tables (`RELKIND_FOREIGN_TABLE`)
  gets no sepgsql check (confirmed)].
- [ISSUE-defense-in-depth: `db_tuple` per-row MAC unimplemented
  (confirmed)].
- [ISSUE-security: parallel workers use server label as scontext
  for parallel-safe function calls (likely)].
- [ISSUE-audit-gap: `db_database:{access}` defined but never fired
  at session establishment (confirmed)].
- [ISSUE-correctness: `SELECT FOR UPDATE` downgrades to
  `db_table:{lock}` only; no per-column checks (verified)].
- [ISSUE-audit-gap: views in plan post-rewrite are rare;
  `db_view:{expand}` check rarely fires (nit)].
- [ISSUE-correctness: `fixup_whole_row_references` skips dropped
  columns — correct (verified)].
- [ISSUE-audit-gap: unknown relkinds silently allow in
  `check_relation_privileges` default (confirmed)].
- [ISSUE-documentation: "Hardwired Policies" comment doesn't note
  enforcing-mode gating (nit)].
