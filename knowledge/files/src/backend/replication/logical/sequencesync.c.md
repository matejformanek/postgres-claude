# `src/backend/replication/logical/sequencesync.c`

- **Last verified commit:** `031904048aa2`
- **Lines:** 815
- **Source:** `source/src/backend/replication/logical/sequencesync.c`

## Purpose

Initial-state synchronization for **sequences** in logical
replication. New in PG 18. Sequences don't have a per-row replication
story; instead the subscriber periodically copies the current value +
log_cnt from the publisher. State machine is the simple
`INIT → READY` per sequence in `pg_subscription_rel`. [from-comment]
(`sequencesync.c:1-49`)

## Trigger points

INIT state is set by `CREATE SUBSCRIPTION`,
`ALTER SUBSCRIPTION ... REFRESH PUBLICATION`, or
`ALTER SUBSCRIPTION ... REFRESH SEQUENCES`. Apply worker periodically
scans for INIT-state sequences and starts a single sequencesync worker
(if none running) via `ProcessSequencesForSync` (`:97`).

## Worker behavior

A single sequencesync worker handles **all** sequences (unlike tablesync,
which is per-rel). It batches up to `MAX_SEQUENCES_SYNC_PER_BATCH`
(= 100, `:441`) per transaction so locks on sequence relations are
released between batches. Per sequence: fetch the publisher value +
page LSN (`REMOTE_SEQ_COL_COUNT = 11` cols, `:75` — including log_cnt,
is_called, and the publisher's `has_sequence_privilege` flag added by
d4a657b0a4db), update local sequence, mark READY.

## Result codes

`CopySeqResult` (`:77-84`): `COPYSEQ_SUCCESS`, `COPYSEQ_MISMATCH`
(e.g. type differs), `COPYSEQ_SUBSCRIBER_INSUFFICIENT_PERM`,
`COPYSEQ_PUBLISHER_INSUFFICIENT_PERM`, `COPYSEQ_SKIPPED`.
[verified-by-code, `:77-84` @ `031904048aa2`]

**Permission misreporting fix (d4a657b0a4db, in this anchor batch).**
The single `INSUFFICIENT_PERM` result was split into a *subscriber*
and a *publisher* variant. The publisher now returns its own
SELECT-privilege flag as the 11th remote column; when the value column
is NULL the subscriber distinguishes "publisher lacks privilege"
(`COPYSEQ_PUBLISHER_INSUFFICIENT_PERM`) from a legitimately-skipped
sequence (`COPYSEQ_SKIPPED`) by that flag (`:302, 340`). Previously a
publisher-side permission failure was misreported as a subscriber-side
one. [verified-by-code, `:296-340` @ `c1702cb51363`]

## Why not the launcher?

Top-of-file XXX: the launcher doesn't have a DB connection so can't
query `pg_subscription_rel`. Hence the apply worker triggers spawning.
(`:46-50`) [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../../architecture/replication.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
