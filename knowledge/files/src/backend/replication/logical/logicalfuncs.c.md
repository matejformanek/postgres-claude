# `src/backend/replication/logical/logicalfuncs.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 389
- **Source:** `source/src/backend/replication/logical/logicalfuncs.c`

## Purpose

SQL SRFs over logical decoding: `pg_logical_slot_get_changes`,
`pg_logical_slot_peek_changes`, `pg_logical_slot_get_binary_changes`,
`pg_logical_slot_peek_binary_changes`. Each acquires a logical slot,
builds a `LogicalDecodingContext` with `logical_read_local_xlog_page` as
its xlog read callback, and loops `LogicalDecodingProcessRecord` until
the requested LSN. Output is materialized into a `Tuplestore` via
`DecodingOutputState` (`:40`). [from-comment]

## Notable

- Wraps callbacks so output_plugin can `pq_send*`-style write into a
  StringInfo; for peek-mode the slot's confirmed_flush is *not* advanced.
- Uses `logical_read_local_xlog_page` from xlogutils — busy-polls a local
  flush LSN; the walsender variant in `walsender.c:logical_read_xlog_page`
  is more efficient.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
