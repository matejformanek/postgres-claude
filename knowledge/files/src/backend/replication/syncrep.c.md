# `src/backend/replication/syncrep.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1150
- **Source:** `source/src/backend/replication/syncrep.c`

## Purpose

Synchronous-replication wait / release machinery, runs entirely on the
primary. Committing backends queue themselves on per-mode dlists keyed by
their commit LSN; walsenders wake them when enough standbys have
acknowledged the LSN. Standbys are oblivious to the durability contract.
[from-comment] (`syncrep.c:1-26`)

## Modes

`SYNC_REP_WAIT_WRITE = 0`, `SYNC_REP_WAIT_FLUSH = 1`,
`SYNC_REP_WAIT_APPLY = 2`, `SYNC_REP_NO_WAIT = -1`. There are 3 separate
queues (`WalSndCtl->SyncRepQueue[NUM_SYNC_REP_WAIT_MODE]`) protected by
`SyncRepLock`. (`syncrep.h:21-27`)

## Standby-selection methods

`FIRST n` (priority-ordered) or `ANY n` (quorum). Parsed by
`syncrep_gram.y` from `synchronous_standby_names`. Backward-compatible
default is FIRST. (`syncrep.c:32-64`) [from-comment]

## Spine functions

- `SyncRepWaitForLSN(lsn, commit)` (`:149`) — called by user backends in
  `CommitTransaction` while interrupts are held. Fast-paths early on
  `SYNC_STANDBY_INIT` without `SYNC_STANDBY_DEFINED` and on
  `lsn <= WalSndCtl->lsn[mode]`. Inserts into the queue sorted by LSN,
  sleeps on `MyLatch`. The wait is uncancellable in the normal sense:
  `ProcDiePending` or `QueryCancelPending` only issue a WARNING and
  terminate the connection — they do *not* roll back. (`:266-372`)
- `SyncRepQueueInsert` (`:382`) — reverse-iterate the dlist; the queue
  invariant is "ordered by ascending waitLSN" so most inserts append.
- `SyncRepReleaseWaiters` (`:484`) — walsender entry; recomputes which
  standbys are sync candidates and pops everyone with `waitLSN <=`
  the just-confirmed LSN.
- `SyncRepGetSyncRecPtr` / `GetOldestSyncRecPtr` / `GetNthLatestSyncRecPtr`
  (`:596`, `:670`, `:703`) — compute the global flush LSN considering
  FIRST vs ANY semantics.
- `SyncRepGetCandidateStandbys` (`:764`) — snapshot of WalSnd states; used
  by the wakers and `pg_stat_replication`.
- `SyncRepUpdateSyncStandbysDefined` (`:973`) — called by checkpointer to
  update `sync_standbys_status` flag in shared memory when GUC changes.

## Invariants

- `SyncRepLock` held exclusive while touching the queue.
- Once a walsender flips `syncRepState = SYNC_REP_WAIT_COMPLETE`, the
  backend is guaranteed not to see a stale value (memory-ordering
  argument at `:280-285`). [from-comment]
- The "cancel-but-warn" semantics are deliberate: the local commit is
  already durable; the contract was about replication, so we don't lie
  by aborting. (`:289-318`) [from-comment]

## Glossary

- **waitLSN** — `PGPROC->waitLSN`; what each waiter is blocked on.
- **syncRepState** — per-PGPROC state: NOT_WAITING / WAITING /
  WAIT_COMPLETE. (`syncrep.h:29-32`)
- **SYNC_STANDBY_{INIT,DEFINED}** — bits in `WalSndCtl->sync_standbys_status`
  letting backends fast-path without `SyncRepLock`. (`walsender_private.h:119-132`)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
