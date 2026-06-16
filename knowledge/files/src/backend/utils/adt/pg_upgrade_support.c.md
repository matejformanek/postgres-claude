# src/backend/utils/adt/pg_upgrade_support.c

## Purpose

Backdoor SQL helpers used **only** by pg_upgrade when restoring catalog
contents into a new cluster. Each function sets a global so the next
catalog insert grabs a specific pre-assigned OID / relfilenumber (rather
than whatever `GetNewOidWithIndex` would pick), or directly performs
otherwise-impossible catalog manipulations (`SetAttrMissing`, adding
`pg_subscription_rel` rows, advancing replication origins, …).

## Role in PG

- Every function is gated by `CHECK_IS_BINARY_UPGRADE`
  (`pg_upgrade_support.c:34-40`) — a macro that throws
  `ERRCODE_CANT_CHANGE_RUNTIME_PARAM` "function can only be called when
  server is in binary upgrade mode" unless the global `IsBinaryUpgrade`
  flag is set. That flag is enabled only when postmaster is started
  with `-b` (the `--binary-upgrade` switch pg_upgrade passes).
- `pg_upgrade` connects as superuser and runs `SET local
  binary_upgrade_*` GUCs + calls these functions inline in the restore
  script.

## Key functions

OID-pinning setters (all trivial — assign to a `binary_upgrade_next_*`
global and return void):
- `binary_upgrade_set_next_pg_tablespace_oid` (`:42-51`)
- `binary_upgrade_set_next_pg_type_oid` / `…_array_…` / `…_multirange_…` /
  `…_multirange_array_…` (`:53-95`)
- `binary_upgrade_set_next_heap_pg_class_oid` /
  `…_heap_relfilenode` (`:97-117`)
- `binary_upgrade_set_next_index_pg_class_oid` /
  `…_index_relfilenode` (`:119-139`)
- `binary_upgrade_set_next_toast_pg_class_oid` /
  `…_toast_relfilenode` (`:141-161`)
- `binary_upgrade_set_next_pg_enum_oid` (`:163-172`)
- `binary_upgrade_set_next_pg_authid_oid` (`:174-182`)

More substantive:
- `binary_upgrade_create_empty_extension(name, schema, relocatable,
  version, config, condition, requires[])` (`:185-247`) — directly
  calls `InsertExtensionTuple()` so pg_upgrade can recreate an
  extension's pg_extension row without re-running the extension's SQL
  install script.
- `binary_upgrade_set_record_init_privs(bool)` (`:249-258`) — tells
  catalog code whether the next ACL change should be recorded as
  "initial privileges" (preserves pre-upgrade GRANTs faithfully).
- `binary_upgrade_set_missing_value(table_id, attname, value)`
  (`:261-273`) — calls `SetAttrMissing` to inject an attmissingval
  for a column added without rewriting an inherited table.
- `binary_upgrade_check_logical_slot_pending_wal(slot_name,
  scan_cutoff_lsn)` (`:285-322`) — pg17+ slot-preservation path;
  acquires the named logical slot and returns the LSN of any
  decodable WAL beyond the slot's `confirmed_flush_lsn`, used to gate
  upgrade.
- `binary_upgrade_add_sub_rel_state(subname, relid, relstate, sublsn)`
  (`:331-367`) — directly writes a `pg_subscription_rel` row.
- `binary_upgrade_replorigin_advance(subname, remote_commit)`
  (`:375-419`) — sets the replication origin's `remote_lsn` so the
  upgraded subscriber resumes from the correct LSN. Does NOT WAL-log
  (`replorigin_advance(..., /*WAL log*/ false)`) — relies on the
  subsequent shutdown checkpoint to flush.
- `binary_upgrade_create_conflict_detection_slot()` (`:428-437`) —
  thin wrapper around `CreateConflictDetectionSlot()`.

## State / globals

- `IsBinaryUpgrade` (in `miscadmin.c`) — toggled by `-b` postmaster arg.
- `binary_upgrade_next_*` globals (declared in
  `catalog/binary_upgrade.h`) — read by catalog allocators in
  `heap.c`/`index.c`/`pg_enum.c` etc. when allocating new OIDs.

## Phase D notes

- **`CHECK_IS_BINARY_UPGRADE` is the *only* defence.** If a user can
  somehow set `IsBinaryUpgrade=true` (they can't — it's not a GUC,
  it's a `bool` flipped on by command-line `-b`), every function here
  becomes a catalog-corruption primitive (assign any OID to any new
  object, fake-restore extensions, inject `attmissingval`s, etc.). The
  comment on `binary_upgrade_check_logical_slot_pending_wal` notes
  "Binary upgrades only allowed super-user connections so we must have
  permission" (`:295-298`) — the assumption is that `-b` plus super-user
  + same-host pg_upgrade is the only realistic invoker.
- `binary_upgrade_add_sub_rel_state` and `…_replorigin_advance`
  comment that lock release is OK because "there are no concurrent
  ALTER/DROP SUBSCRIPTION commands during the upgrade process, and the
  apply worker … is not running" (`:357-361`). True under
  `pg_upgrade --check`-style use, **false if a malicious caller
  somehow re-enters binary upgrade mode mid-replication**. The
  defence-in-depth assumption: -b mode is mutually exclusive with
  normal operation.
- `binary_upgrade_replorigin_advance` (`:411-413`) deliberately passes
  `WAL log = false`. This means the change is durable only via the
  shutdown checkpoint. If the cluster crashes mid-upgrade after this
  call, the origin advance is lost — but the upgrade as a whole is
  not survivable across a crash anyway.

## Potential issues

- [ISSUE-trust-boundary: every function here is a catalog-corruption
  primitive if `IsBinaryUpgrade` is ever toggled outside the
  postmaster `-b` startup path. The defence is a single boolean, set
  once. No second layer (no superuser re-check, no schema-of-caller
  validation) (HIGH conditional, but currently sound) ]
- [ISSUE-undocumented-invariant: `binary_upgrade_create_empty_extension`
  doesn't validate that the schemaName / version pair makes sense for
  the named extension — pg_upgrade is trusted to pass coherent values.
  A buggy / hand-crafted dump could create a pg_extension row whose
  control file says otherwise (low)]
- [ISSUE-state-transition: `binary_upgrade_replorigin_advance` skips
  WAL — relies on subsequent shutdown checkpoint; crash before that
  loses the advance silently (low, by design)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
