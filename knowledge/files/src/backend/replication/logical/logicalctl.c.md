# `src/backend/replication/logical/logicalctl.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 637
- **Source:** `source/src/backend/replication/logical/logicalctl.c`

## Purpose

Dynamic control of logical decoding availability when
`wal_level=replica`. Splits "write logical info into WAL" from "use
logical decoding" so the two can be toggled separately; reflected in the
read-only `effective_wal_level` GUC. Activation is synchronous (right
after first logical slot creation); deactivation is asynchronous via the
checkpointer, partly to avoid an end-of-recovery race
(`UpdateLogicalDecodingStatusEndOfRecovery`) and partly to avoid thrash
on slot churn. [from-comment] (`logicalctl.c:1-54`)

## Why not always-on logical?

`wal_level=logical` has measurable overhead from `XLOG_HEAP2_NEW_CID`
records and extra invalidation distribution. PG 18 makes it possible to
keep `wal_level=replica` and only "promote" to logical when a slot
actually exists.

## Standby behavior

Standbys mirror the primary's `effective_wal_level` and logical-decoding
status via `XLOG_LOGICAL_DECODING_STATUS_CHANGE` records; the standby's
local `wal_level` GUC is ignored until promotion, at which point the
status is recomputed based on local conditions.

## Public surface

Functions like `IsLogicalDecodingEnabled`, `LogicalDecodingActivate`,
`LogicalDecodingDeactivate`, `UpdateLogicalDecodingStatusEndOfRecovery`
(referenced from `slot.c`, `xlog.c`). Header is
`replication/logicalctl.h`.

## Future work

Top comment notes that automatic `minimal ↔ logical` transitions would
need more coordination (terminate walsenders, archivers). [from-comment]
