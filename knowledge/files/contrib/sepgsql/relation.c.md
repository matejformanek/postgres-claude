# relation.c

## One-line summary

`db_table`/`db_sequence`/`db_view`/`db_column` class hooks: per-relation
and per-attribute labels + the `create/drop/setattr/relabel/truncate`
permission checks (DML checks live in dml.c). Indexes are treated as
attributes of their owning table.

## Public API / entry points

- `sepgsql_attribute_post_create(relOid, attnum) → void` —
  `source/contrib/sepgsql/relation.c:42-125`. Per-column label assign on
  ALTER TABLE ... ADD COLUMN. **NOT invoked for columns added at CREATE
  TABLE** (comment, relation.c:39-40) — those are labeled inside
  `sepgsql_relation_post_create`.
- `sepgsql_attribute_drop(relOid, attnum) → void` — `relation.c:132-156`.
  Checks `db_column:{drop}`.
- `sepgsql_attribute_relabel(relOid, attnum, seclabel) → void` —
  `relation.c:164-201`.
- `sepgsql_attribute_setattr(relOid, attnum) → void` — `relation.c:208-232`.
- `sepgsql_relation_post_create(relOid) → void` — `relation.c:239-408`.
  The heaviest function: dispatches on relkind, computes labels for the
  relation AND every column.
- `sepgsql_relation_drop(relOid) → void` — `relation.c:415-516`.
- `sepgsql_relation_truncate(relOid) → void` — `relation.c:523-556`.
- `sepgsql_relation_relabel(relOid, seclabel) → void` —
  `relation.c:563-607`.
- `sepgsql_relation_setattr(relOid) → void` — `relation.c:614-709`.

Static helpers:

- `sepgsql_relation_setattr_extra` — `relation.c:720-751`. Indirect setattr
  check via index → table lookup.
- `sepgsql_index_modify(indexOid)` — `relation.c:761-773`. Indexes have no
  labels; checks `db_table:{setattr}` on the owning table instead.

## Key invariants

- Only `RELKIND_RELATION` and `RELKIND_PARTITIONED_TABLE` get per-column
  labels (`relation.c:61-62, 139-140, 215-216, 350-351, 486`). Views,
  sequences, foreign tables: no column labels. [verified-by-code]
- TOAST indexes (`relkind == INDEX && relnamespace == PG_TOAST_NAMESPACE`)
  are skipped entirely (`relation.c:276-279, 437-438`). [verified-by-code]
- The relkind dispatch in `post_create` falls through to `goto out` on
  unknown kinds (`relation.c:310-311`) — silent skip.
- `sepgsql_index_modify` is the *only* code path for index permission
  checks; indexes have no labels.
- The relkind→tclass mapping is:
  - `RELATION`, `PARTITIONED_TABLE` → `SEPG_CLASS_DB_TABLE`
  - `SEQUENCE` → `SEPG_CLASS_DB_SEQUENCE`
  - `VIEW` → `SEPG_CLASS_DB_VIEW`
  Any other relkind is unmonitored. [verified-by-code]

## Notable internals

`sepgsql_relation_post_create` flow:

1. SnapshotSelf-scan pg_class for new tuple.
2. Skip if TOAST index (`relation.c:277-279`).
3. Check `db_schema:{add_name}` on the relation's namespace
   (`relation.c:283-291`).
4. Dispatch on relkind to determine tclass; for INDEX, call
   `sepgsql_index_modify` and `goto out`.
5. Compute new relation label via `sepgsql_compute_create(client,
   schema_label, tclass, relname)`.
6. Check `db_xxx:{create}` against new label.
7. `SetSecurityLabel` on the relation.
8. *For RELATION/PARTITIONED_TABLE only:* iterate pg_attribute, compute
   per-column labels (parent = relation's new label), check
   `db_column:{create}` on each, `SetSecurityLabel` each. This is the
   O(N_columns) per-table loop (`relation.c:359-401`).

`sepgsql_relation_drop` flow:

1. Resolve relkind, map to tclass.
2. Check `db_schema:{remove_name}` on namespace
   (`relation.c:449-459`).
3. If INDEX, delegate to `sepgsql_index_modify` and return.
4. Check `db_table/view/sequence:{drop}` (`relation.c:476-481`). Note the
   bug-prone `SEPG_DB_TABLE__DROP` constant is used unconditionally even
   for sequence and view tclasses — this works because
   `SEPG_DB_TABLE__DROP == SEPG_DB_DATABASE__DROP == (1<<1)` and all the
   `__DROP` macros alias the same bit (`sepgsql.h:138, 151, 161, 188,
   199, 208`). So this is correct but reads as if there's a constant
   mismatch.
5. For RELATION/PARTITIONED_TABLE, iterate columns via
   `SearchSysCacheList1(ATTNUM, relOid)`, skip dropped columns, check
   `db_column:{drop}` per (`relation.c:486-515`).

`sepgsql_attribute_relabel` has a likely **bug**: the relabelto check uses
`SEPG_DB_PROCEDURE__RELABELTO` (`relation.c:197`) when it should be
`SEPG_DB_COLUMN__RELABELTO`. The values are equal (both `1<<5` per the
header definitions), so behavior is correct, but the name is wrong. The
audit text via `selinux_catalog[]` is keyed by tclass anyway so audit
output stays correct. [ISSUE-correctness: relation.c:197 uses
`SEPG_DB_PROCEDURE__RELABELTO` macro inside a db_column check; works only
because the bit values alias (confirmed)]

`sepgsql_relation_setattr` does an old-vs-new pg_class compare:

- If `relnamespace` changed: check remove_name on old NS, add_name on new
  NS (`relation.c:678-682`).
- If `relname` changed: check schema rename on the old NS
  (`relation.c:683-684`).
- Always check `db_xxx:{setattr}` on the relation (`relation.c:699-703`).
- For indexes, delegate to `sepgsql_index_modify` and return early.

`sepgsql_index_modify` calls `sepgsql_relation_setattr_extra` with
`Anum_pg_index_indrelid` to find the owning table and check setattr on
that. This is also called from `OAT_POST_ALTER` on indexes via
`sepgsql_relation_setattr` (`relation.c:640-643`).

## Trust boundary / Phase D surface

- **Per-column-create loop is O(N_columns) per table create** — for a
  table with hundreds of columns this is N AVC checks (each potentially
  a cache lookup, possibly a libselinux call on miss). The cache
  amortizes well if all columns get the same label. [verified-by-code]

- **Per-row DML checks DO NOT happen here.** This file is DDL-only.
  Row/tuple-level enforcement is documented in sepgsql.h as `db_tuple`
  but is not wired in the current implementation. The comment at
  `relation.c:687-689` ("XXX - In the future version, db_tuple:{use}
  of system catalog entry shall be checked") confirms this — db_tuple
  class is *defined but unused*. [verified-by-code]

- **Index labels skipped.** `sepgsql_index_modify` delegates to the
  table's setattr. **Consequence**: an attacker who can label a table
  cannot label the index separately, but the index *includes data
  from the table*, so the table's label is the right thing to gate.
  Standard pattern. [verified-by-code]

- **The `db_table:{select}` permission applies to the whole table,
  not per-row.** Per-column `db_column:{select}` is the finest
  granularity (dml.c). For row-level MAC, sepgsql is not the right
  tool — the `db_tuple` class is unimplemented. [verified-by-code]

- **`relation_drop` checks `db_schema:{remove_name}` on the namespace
  *first*, then per-class drop, then per-column drop.** Ordering
  ensures the schema-level check fires first and can deny before
  expensive per-column work. **However**, the per-column drop is
  *unconditional* on relkind once we're past the namespace check —
  if a future contributor adds a new relkind that gets columns
  (foreign tables already have columns!), the column drop check
  would either fail to fire (if relkind not in the
  RELATION/PARTITIONED_TABLE check) or fire unexpectedly.
  Foreign tables: `RELKIND_FOREIGN_TABLE` is not in any case → no
  column label, no column drop check. [ISSUE-audit-gap: foreign
  tables have columns but no per-column sepgsql labels or checks
  (likely)]

- **`SetSecurityLabel` is called inside the loop in
  `sepgsql_relation_post_create`**, doing N catalog writes for an
  N-column table. Each write is a heap_update on pg_seclabel. This
  is observable as a write-amplification of CREATE TABLE under
  sepgsql. [verified-by-code]

- **`getObjectIdentity(&object, false)` allocates audit names in
  a tight loop** (`relation.c:494-512`). Each pfree happens after
  the AVC check, so steady-state memory is OK, but allocator
  churn is notable for wide tables.

- **`sepgsql_relation_setattr` reads both the old (syscache) and new
  (SnapshotSelf) pg_class rows.** Necessary because some ALTER paths
  install the new tuple before the hook fires (rename, reschema).
  This pattern leaks if any error fires between the table_open and
  the table_close — the
  `ReleaseSysCache(oldtup); systable_endscan; table_close` cleanup
  isn't inside a PG_TRY (`relation.c:706-708`). Reachable only via
  AVC denial which aborts the transaction — so the resource leak is
  cleaned by xact-end. [verified-by-code]

- **Truncate is gated only on `db_table:{truncate}` for ordinary
  tables**, but the per-column SELECT/UPDATE doesn't fire — truncate
  is whole-table, not row-level. Consistent. [verified-by-code]

- **TOAST index skip via OID-namespace test** (`relation.c:277-278`):
  if a future contributor stops using `PG_TOAST_NAMESPACE` for TOAST
  indexes, this check would silently let TOAST index creation
  fall through to permission checks. Defensive, but tightly coupled
  to existing catalog convention. [verified-by-code]

- **Partitioned-table partition labels.** Adding a partition fires
  `OAT_POST_CREATE` on the new partition (a RELATION). The parent
  partitioned table's label is *not* used as tcontext —
  `sepgsql_relation_post_create` uses the *schema's* label
  (`relation.c:319-321`). So partitions don't inherit from the
  partitioned-table label, they inherit from the schema. Policy
  authors must encode partition inheritance separately.
  [ISSUE-defense-in-depth: partitions inherit from schema label,
  not from the partitioned table's label; cross-partition label
  consistency is policy-burden (likely)]

- **Index permission via the *table* setattr** means a SECURITY
  LABEL change on the table affects index DDL permission, even
  though the index has no label of its own. There's no surprise
  here for an attacker, but operators should know.

- **Internal-rebuild gate via `is_internal`** (hooks.c:132). Index
  rebuild during ALTER TABLE doesn't trigger sepgsql post_create;
  this is the only way a TOAST-table rebuild stays unaudited.

## Cross-references

- hooks.c — dispatcher.
- uavc.c — `sepgsql_avc_check_perms{,_label}`.
- selinux.c — `sepgsql_compute_create`.
- label.c — `sepgsql_get_label`, `sepgsql_get_client_label`.
- dml.c — companion file for DML-time per-column checks.
- `source/src/backend/commands/tablecmds.c` — ALTER TABLE path,
  invokes OAT hooks.
- `source/src/include/catalog/pg_class.h`,
  `source/src/include/catalog/pg_attribute.h` — catalog formdef.

## Issues spotted

- `[ISSUE-correctness: relation.c:197 passes SEPG_DB_PROCEDURE__RELABELTO
  into a db_column relabelto check; works because bit values alias
  (confirmed)]`
- `[ISSUE-audit-gap: foreign tables have columns but no per-column
  sepgsql labels; RELKIND_FOREIGN_TABLE is not in the
  RELATION/PARTITIONED_TABLE checks (likely)]`
- `[ISSUE-defense-in-depth: partitions inherit from schema label, not
  from the partitioned-table label; cross-partition consistency is
  policy-burden (likely)]`
- `[ISSUE-audit-gap: unknown relkinds in post_create/drop/setattr
  silently goto out / return without check or audit (confirmed)]`
- `[ISSUE-memory: getObjectIdentity in tight per-column loops creates
  short-lived strings; per-table linear allocation churn (nit)]`
- `[ISSUE-correctness: SEPG_DB_TABLE__DROP is reused for sequence/view
  drop checks (relation.c:478); aliasing happens to work but reads
  as if a constant is wrong (nit)]`
- `[ISSUE-correctness: TOAST index skip relies on PG_TOAST_NAMESPACE
  conventions; brittle to future TOAST refactors (nit)]`
- `[ISSUE-audit-gap: ALTER TABLE rebuild paths set is_internal=true;
  sepgsql skips them — index rebuild does not re-audit (confirmed by
  comment relation.c:124-131)]`
- `[ISSUE-documentation: db_tuple class is defined in sepgsql.h but
  not wired in dml.c or relation.c; the future-version comment
  (relation.c:687) is years old (nit)]`
- `[ISSUE-correctness: sepgsql_relation_setattr resource cleanup
  (ReleaseSysCache, table_close) not in PG_TRY — relies on xact
  cleanup if an unexpected error fires between (nit)]`
- `[ISSUE-correctness: per-attribute-post-create only fires on
  ALTER TABLE ADD COLUMN, not CREATE TABLE; CREATE TABLE column
  labels are computed inside sepgsql_relation_post_create — two
  code paths that must stay in sync if a contributor changes one
  (likely)]`
