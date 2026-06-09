# dml.c

## One-line summary

DML-time permission checks via the `ExecutorCheckPerms_hook`: maps
PG's per-RTE `selectedCols/insertedCols/updatedCols` Bitmapsets to
`db_table:{select|insert|update|delete|lock}` and per-column
`db_column:{select|insert|update}` AVC checks, plus the two
"hardwired" policies blocking DML on catalogs and TOAST.

## Public API / entry points

- `sepgsql_dml_privileges(rangeTbls, rteperminfos, abort_on_violation) →
  bool` — `source/contrib/sepgsql/dml.c:281-359`. Called by
  `sepgsql_exec_check_perms` in hooks.c. Iterates `rteperminfos`, derives
  required perm bitmap from `ACL_SELECT/INSERT/UPDATE/DELETE`, and for
  each relation (expanded across inheritance) calls
  `check_relation_privileges`.

Static helpers:

- `fixup_whole_row_references(relOid, Bitmapset *) → Bitmapset *` —
  `dml.c:38-80`. Expands a whole-row Var bit into a bitmap of all
  non-dropped columns.
- `fixup_inherited_columns(parentId, childId, Bitmapset *) → Bitmapset *`
  — `dml.c:92-133`. Translates parent attnos to child attnos via
  attribute-name lookup.
- `check_relation_privileges(relOid, selected, inserted, updated,
  required, abort) → bool` — `dml.c:141-274`. The per-relation check
  driver.

## Key invariants

- Hooked via `ExecutorCheckPerms_hook` (hooks.c:478), so this fires
  *during* executor startup, after the planner has finalized the
  rteperminfos. [verified-by-code]
- `ACL_UPDATE` without any `updatedCols` is downgraded to a *lock-only*
  check (`required |= SEPG_DB_TABLE__LOCK`) rather than UPDATE
  (`dml.c:302-307`). This handles `SELECT ... FOR UPDATE` correctly.
  [verified-by-code]
- Inheritance hierarchy expansion via `find_all_inheritors(relid,
  NoLock, NULL)` when `perminfo->inh` is true (`dml.c:323-326`). Each
  child relation gets its own attribute-bitmap fixup.
- `abort_on_violation` is propagated from the hook caller (executor)
  through to the AVC check; if false, returns bool. If true (default
  via `ExecCheckPermissions`), denies raise `ereport(ERROR,
  INSUFFICIENT_PRIVILEGE)` from `sepgsql_avc_check_perms`.
  [verified-by-code]

## Notable internals

`check_relation_privileges` flow:

1. **Hardwired denial when enforcing**:
   - `IsCatalogRelationOid(relOid)` and required has any of
     INSERT/UPDATE/DELETE → ereport ERROR with "hardwired security
     policy violation" (`dml.c:161-169`).
   - `relkind == RELKIND_TOASTVALUE` → same error (`dml.c:171-174`).
   Both checks short-circuit if `sepgsql_getenforce() == 0`.
   [verified-by-code]

2. **Per-relation table-level check**:
   - `RELATION`/`PARTITIONED_TABLE` → `db_table:{required}` check.
   - `SEQUENCE` → maps `SELECT` to `db_sequence:{get_value}`. All
     other perms on sequences are silently ignored. The Assert at
     `dml.c:196` enforces that only SELECT can be required for a
     sequence (i.e., DML INSERT/UPDATE/DELETE on a sequence is a
     planner-time mistake).
   - `VIEW` → `db_view:{expand}`. A view in the plan means it
     hadn't been expanded by rewrite — typically auto_explain or
     `security_invoker` paths.
   - Other relkinds: no check, `result = true`. [verified-by-code]

3. **Per-column check** (only for RELATION/PARTITIONED_TABLE):
   - Whole-row references in `selected/inserted/updated` are expanded
     via `fixup_whole_row_references`.
   - Iterate the union of the three bitmaps.
   - For each column, build a `db_column:{}` perm mask from the
     three bitmaps. Note: `INSERT` and `UPDATE` column perms are
     *only* added if the parent table-level `required` includes the
     corresponding `INSERT`/`UPDATE` bit (`dml.c:244-251`). So a
     pure SELECT path doesn't fire per-column INSERT/UPDATE checks.
   - If `column_perms == 0`, skip.
   - `sepgsql_avc_check_perms` on the column object.

4. **Inheritance expansion** in `sepgsql_dml_privileges`: parent's
   bitmap → each child's bitmap via name-based translation
   (`dml.c:339-344`). If a child lacks a column the parent has, the
   `get_attnum` lookup is wrapped in `elog(ERROR, ...)` —
   theoretically unreachable since inheritance enforces matching
   columns.

## Trust boundary / Phase D surface

- **THIS IS the row-level filter?** *No.* Despite section 6 of the
  prompt asking about row-level filtering, sepgsql does NOT do
  per-row filtering. It does *per-column* checks for the
  *projection* and per-table checks. The `db_tuple` class is
  defined in sepgsql.h but never used (search for it: only
  references are in the header). Row-level MAC in sepgsql remains
  a TODO (`relation.c:687-689` "XXX - In the future version,
  db_tuple:{use} ... shall be checked"). [verified-by-code]
  [ISSUE-defense-in-depth: db_tuple per-row MAC is unimplemented;
  sepgsql is column-granularity only (confirmed)]

- **Hardwired catalog/TOAST denial bypassed in PERMISSIVE.** The
  `sepgsql_getenforce() > 0` guard (`dml.c:161`) means in
  permissive/internal mode the catalog and TOAST DML denials do
  not fire. So in permissive mode, a user *could* INSERT into
  pg_class if PG-side ACL allows (it normally doesn't —
  superuser-only). **Defense in depth lost in permissive.**
  [ISSUE-defense-in-depth: hardwired catalog/TOAST DML denial
  fires only when sepgsql_getenforce() > 0 — permissive mode
  loses this protection (likely)]

- **Parallel-worker behavior.** `ExecutorCheckPerms_hook` fires
  in `ExecCheckPermissions`, which is called from the *leader*
  during `ExecutorStart`. Parallel workers spawned later get
  their executor state through DSM; they do *not* re-invoke
  `ExecCheckPermissions`. So DML permission checks fire ONCE
  in the leader. Sepgsql does *not* re-check in workers. This
  is correct — the leader's check covers the access — but
  combined with the label.c finding (parallel-worker client_label
  is the server label), worker-side checks via other paths
  (e.g., `sepgsql_proc_execute` for a function called inside a
  parallel-safe plan node) would use the wrong scontext.
  [ISSUE-security: parallel-safe functions invoked in workers
  go through OAT_FUNCTION_EXECUTE with the worker's
  client_label = server label, not the originating client's
  label (likely)]

- **Direct foreign-modify (postgres_fdw bulk push-down).** When
  postgres_fdw pushes DML to a remote server, the *local*
  `ExecutorCheckPerms_hook` still fires once for the foreign
  table's RTE (relkind FOREIGN_TABLE). `check_relation_privileges`
  hits the default branch at `dml.c:214-216` — **no check
  performed**, `result = true`. Per-column checks are skipped
  (relkind != RELATION). **So sepgsql is silent on foreign-table
  DML.** [ISSUE-security: DML on foreign tables (relkind
  FOREIGN_TABLE) gets no sepgsql check beyond the implicit
  RTE-level ACL_xxx mapping; per-column foreign access is
  unaudited (confirmed)]

- **Index-only scans.** No relation in the RTE list is an
  index — index-only scans still reference the underlying
  relation OID. The leader's RTE check covers them.
  [verified-by-code]

- **`fixup_whole_row_references` allocates a fresh Bitmapset**
  (`dml.c:60-79`). The original `selected/inserted/updated`
  Bitmapsets in `perminfo` are not modified — well, actually:
  the code does `selected = fixup_whole_row_references(relOid,
  selected)` (`dml.c:229`), which returns the *original*
  pointer if there was no whole-row ref (`dml.c:48-50`). So if
  the caller's bitmap had a whole-row reference, `selected` now
  points to a fresh bitmap; otherwise it points to
  `perminfo->selectedCols`. No mutation of the input. Good.
  [verified-by-code]

- **`fixup_inherited_columns` raises elog(ERROR)** on attribute-
  name lookup miss (`dml.c:122-124`). For a parent column that
  doesn't exist in the child, this kills the query. This should
  be unreachable in a well-formed inheritance hierarchy.
  [verified-by-code]

- **Column-create label vs DML column-check ordering.** A column
  added via ALTER TABLE ADD COLUMN gets a label via
  `sepgsql_attribute_post_create`. Until then, the column is
  unlabeled. The DML check fires on every executor entry — if
  a SELECT executes before the post_create finishes (impossible
  in one txn), the column would be unlabeled. Within a single
  xact this is correct. [verified-by-code]

- **`required == 0` short-circuit** (`dml.c:313-315`). RTEs that
  don't actually grant any of SELECT/INSERT/UPDATE/DELETE skip
  the relation entirely — e.g., `LATERAL` references that don't
  read any column.

- **Audit_name in the per-column loop uses `getObjectDescription`
  not `getObjectIdentity`** (`dml.c:261`). Description is more
  human-friendly ("column foo of table public.bar"). The
  per-relation check uses `getObjectIdentity` (`dml.c:183`). The
  inconsistency is cosmetic but two different label-formatting
  paths exist. [verified-by-code]

- **No db_database:{access} check on the connecting database
  in DML.** That check would fire at session start; sepgsql
  doesn't have a session-start hook beyond `ClientAuthentication`,
  and `sepgsql_client_auth` doesn't audit a db-access perm.
  PG-side ACL handles database connect. [ISSUE-audit-gap: no
  db_database:{access} check at session establishment; defined
  in sepgsql.h but never fired (confirmed)]

## Cross-references

- hooks.c — `sepgsql_exec_check_perms` → `sepgsql_dml_privileges`.
- uavc.c — `sepgsql_avc_check_perms`.
- relation.c — companion DDL-time checks.
- `source/src/backend/executor/execMain.c` —
  `ExecutorCheckPerms_hook` invocation site
  (`ExecCheckPermissions`).
- `source/src/backend/parser/parsetree.c` — `RTEPermissionInfo`
  structure.
- `source/src/backend/catalog/heap.c` —
  `find_all_inheritors`.

## Issues spotted

- `[ISSUE-defense-in-depth: hardwired catalog/TOAST DML denial
  gated on sepgsql_getenforce() > 0 — permissive mode loses
  this protection (likely)]`
- `[ISSUE-security: DML on foreign tables (RELKIND_FOREIGN_TABLE)
  gets no sepgsql per-relation or per-column check (confirmed)]`
- `[ISSUE-defense-in-depth: db_tuple per-row MAC is unimplemented
  (confirmed)]`
- `[ISSUE-security: parallel workers use server label as scontext;
  parallel-safe function calls in workers go through OAT execute
  hook with the wrong subject (likely)]`
- `[ISSUE-audit-gap: db_database:{access} is defined in sepgsql.h
  but never fired at session establishment (confirmed)]`
- `[ISSUE-correctness: SELECT FOR UPDATE downgrades to
  db_table:{lock} only — db_column checks are not added
  (dml.c:302-307) because column_perms gates on parent
  required bits; intentional but worth noting (verified)]`
- `[ISSUE-audit-gap: views in the plan post-rewrite are rare
  (view expansion happens in rewriter); the db_view:{expand}
  check is only meaningful for security_invoker views and
  certain RLS interactions (nit)]`
- `[ISSUE-correctness: fixup_whole_row_references skips dropped
  columns (dml.c:71) — a relabel-then-drop sequence leaves
  the bitmap pointing at the right post-drop attribute set
  (verified)]`
- `[ISSUE-audit-gap: result returned from check_relation_privileges
  is true even when relkind is unknown — the default branch
  (dml.c:214-216) silently allows (confirmed)]`
- `[ISSUE-documentation: comment in dml.c:157-160 says "Hardwired
  Policies" — the sepgsql docs should highlight that they
  apply only in enforcing mode (nit)]`
