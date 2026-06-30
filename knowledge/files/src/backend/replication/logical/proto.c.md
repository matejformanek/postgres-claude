# `src/backend/replication/logical/proto.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1304
- **Source:** `source/src/backend/replication/logical/proto.c`

## Purpose

Wire-format reader/writer for the logical-replication on-the-wire protocol.
One function pair per `LogicalRepMsgType` ('B' BEGIN, 'C' COMMIT, 'I'/U/D,
'T' TRUNCATE, 'R' RELATION, 'Y' TYPE, 'M' MESSAGE, 'O' ORIGIN, 'b' BEGIN
PREPARE, 'P' PREPARE, 'K' COMMIT PREPARED, 'r' ROLLBACK PREPARED, 'S'/E/A/p/c
streamed-xact messages). Pgoutput on the publisher writes via
`logicalrep_write_*`; the apply worker reads via `logicalrep_read_*`.
[from-comment]

## Notable flags

- `LOGICALREP_IS_REPLICA_IDENTITY` (`:26`) — column-attr bit.
- `TRUNCATE_CASCADE`, `TRUNCATE_RESTART_SEQS` (`:29-30`) — truncate flags.
- `MESSAGE_TRANSACTIONAL` (`:28`) — message flag.

## Tuple-data wire format

`LogicalRepTupleData.colstatus` byte per column: 'n' (NULL),
'u' (UNCHANGED — TOAST/key-only), 't' (text), 'b' (binary, added in PG
14). (`logicalproto.h:96-99`)

## Protocol versions

- v1 — baseline (PG 10)
- v2 — streaming of in-progress xacts (PG 14)
- v3 — two-phase commits (PG 15)
- v4 — parallel streaming apply (PG 16)

Constants in `logicalproto.h:40-45`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
- [idioms/apply-handlers-insert-update-delete.md](../../../../../idioms/apply-handlers-insert-update-delete.md)
- [idioms/apply-worker-loop-and-dispatch.md](../../../../../idioms/apply-worker-loop-and-dispatch.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->

