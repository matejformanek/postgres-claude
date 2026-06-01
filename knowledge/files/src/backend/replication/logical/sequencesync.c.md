# `src/backend/replication/logical/sequencesync.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 776
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
(if none running) via `ProcessSequencesForSync` (`:96`).

## Worker behavior

A single sequencesync worker handles **all** sequences (unlike tablesync,
which is per-rel). It batches up to `MAX_SEQUENCES_SYNC_PER_BATCH` per
transaction so locks on sequence relations are released between batches.
Per sequence: fetch the publisher value + page LSN (REMOTE_SEQ_COL_COUNT
= 10 cols including log_cnt and is_called), update local sequence,
mark READY.

## Result codes

`CopySeqResult` (`:77-83`): SUCCESS, MISMATCH (e.g. type differs),
INSUFFICIENT_PERM, SKIPPED.

## Why not the launcher?

Top-of-file XXX: the launcher doesn't have a DB connection so can't
query `pg_subscription_rel`. Hence the apply worker triggers spawning.
(`:46-49`) [from-comment]
