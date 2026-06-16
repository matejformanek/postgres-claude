# replnodes.h

- **Source:** `source/src/include/nodes/replnodes.h` (~130 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Parse-node types for the **replication command grammar** spoken on
the walsender / replication wire protocol — not the same grammar as
the SQL frontend. Each one corresponds to one command in
`repl_gram.y`.

## ReplicationKind `:20-24`

```
REPLICATION_KIND_PHYSICAL
REPLICATION_KIND_LOGICAL
```

## Command nodes

- `IdentifySystemCmd` `:31` — `IDENTIFY_SYSTEM`
- `BaseBackupCmd` `:41` — `BASE_BACKUP` (with options list)
- `CreateReplicationSlotCmd` `:52` — `CREATE_REPLICATION_SLOT`
- `DropReplicationSlotCmd` `:67` — `DROP_REPLICATION_SLOT`
- `AlterReplicationSlotCmd` `:79` — `ALTER_REPLICATION_SLOT`
- `StartReplicationCmd` `:91` — `START_REPLICATION` (kind, slotname,
  startpoint, timeline, options)
- `ReadReplicationSlotCmd` `:106` — `READ_REPLICATION_SLOT`
- `TimeLineHistoryCmd` `:117` — `TIMELINE_HISTORY`
- `UploadManifestCmd` `:127` — `UPLOAD_MANIFEST`

Each just contains the few command parameters; no further structure.

## Cross-references

- Grammar: `src/backend/replication/repl_gram.y`,
  `src/backend/replication/repl_scanner.l`.
- Dispatch: `src/backend/replication/walsender.c exec_replication_command`.
- Logical decoding side: `src/backend/replication/logical/`.

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->
