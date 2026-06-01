# `src/backend/storage/sync/sync.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 621
- **Source:** `source/src/backend/storage/sync/sync.c`

## Purpose

The fsync request queue used by the checkpointer to absorb backend
write activity and issue the resulting fsyncs at checkpoint time.
Backends call `RegisterSyncRequest(FileTag, type)`; if running under
the postmaster, this forwards via shared-memory IPC to the
checkpointer; in standalone or startup-process mode, the request is
applied to the local `pendingOps` hashtable directly. At checkpoint,
the checkpointer drains `pendingOps` and calls the appropriate
handler's `sync_syncfiletag` (e.g. `mdsyncfiletag`) for each entry.
[from-comment] (`sync.c:1-54`)

## Top of file

The pendingOps hashtable + pendingUnlinks list exist *only* in
processes that own a sync responsibility — the checkpointer and
standalone backends. Normal backends keep no local copy; they forward
all requests to the checkpointer immediately. (lines 36–54)

## Public surface (sync.h)

- `InitSync(void)` — set up `pendingOps` if we are a checkpointer or
  standalone process.
- `SyncPreCheckpoint(void)` — call before determining REDO point.
- `SyncPostCheckpoint(void)` — process pending unlinks.
- `ProcessSyncRequests(void)` — the checkpoint-time drain.
- `RememberSyncRequest(FileTag *, type)` — local apply (called by
  the checkpointer when absorbing forwarded requests).
- `RegisterSyncRequest(FileTag *, type, bool retryOnError) → bool`
  — the caller-facing entry point.

## Types

- `PendingFsyncEntry` (lines 57–62): {tag, cycle_ctr, canceled}.
  Hashed by tag in `pendingOps`.
- `PendingUnlinkEntry` (lines 64–69): same fields but lives in a
  list, since dedup is unnecessary.
- `SyncOps` (lines 85–91): per-handler vtable
  (`sync_syncfiletag`/`sync_unlinkfiletag`/`sync_filetagmatches`).
- `syncsw[]` (lines 96–119): one entry per `SyncRequestHandler`
  (MD, CLOG, COMMIT_TS, MULTIXACT_OFFSET, MULTIXACT_MEMBER).
- `FileTag` (sync.h): `handler` + `forknum` + `rlocator` + `segno`
  — opaque to sync.c (it just hashes by it).

## SyncRequestType

(from `sync.h:23-29`)
- `SYNC_REQUEST` — enqueue an fsync.
- `SYNC_UNLINK_REQUEST` — enqueue a deferred unlink.
- `SYNC_FORGET_REQUEST` — cancel any matching fsync.
- `SYNC_FILTER_REQUEST` — cancel everything where
  `sync_filetagmatches(ftag, candidate)` is true (used by DROP
  DATABASE).

## Functions of note

**`RegisterSyncRequest` (lines 580–620)**: if `pendingOps` is set
(checkpointer / standalone), apply locally; else call
`ForwardSyncRequest` (defined in `bgwriter.c`/IPC layer). On full
queue, either retry with a 10ms sleep or return false depending on
`retryOnError`.

**`RememberSyncRequest` (lines 487–572)**: dispatches by type:
- SYNC_FORGET_REQUEST: find entry, set `canceled = true`.
- SYNC_FILTER_REQUEST: walk both hash and list, mark matches
  canceled. Used during DROP DATABASE.
- SYNC_UNLINK_REQUEST: append `PendingUnlinkEntry` to list with
  current `checkpoint_cycle_ctr`.
- SYNC_REQUEST (default): hash_search HASH_ENTER; if new or
  previously canceled, set `cycle_ctr = sync_cycle_ctr` and
  `canceled = false`. **Intentionally does not update cycle_ctr if
  the entry already exists** — the stored cycle_ctr must represent
  the *oldest* fsync request that the entry covers, so a later write
  cannot make a stale request look fresh. [from-comment]
  (`sync.c:564-568`)

**`ProcessSyncRequests` (lines 287–476)**: the checkpoint drain.
Calls `AbsorbSyncRequests` first so any backend-forwarded request
queued before checkpoint start gets processed. Increments
`sync_cycle_ctr`; any entry with the *new* counter is "too new" and
skipped until next checkpoint. Loops the hashtable, fsyncs each
non-canceled entry via `syncsw[handler].sync_syncfiletag`. On
ENOENT it absorbs and retries (mdunlink queues a "cancel" before
unlinking, so by the time we retry the cancellation should be
visible). Wraparound protection: if a previous drain failed,
forcibly resets all cycle_ctrs to current before continuing
(lines 326–354). Reports CheckpointStats at end.

**`SyncPreCheckpoint` (lines 178–195)**: bumps
`checkpoint_cycle_ctr` so any unlink request arriving after this
will be processed by the *next* checkpoint, not this one. Must be
called before REDO point determination. (`sync.c:174-195`)

**`SyncPostCheckpoint` (lines 203–281)**: walks `pendingUnlinks`,
unlinking each non-canceled entry whose cycle_ctr ≠ current. Bails
early when it sees an entry with the current cycle_ctr (FIFO order).
Periodically re-absorbs in case backends are filling the queue.

## Invariants

- `pendingOps` exists only in standalone backends and the
  checkpointer. Anyone else calling `RememberSyncRequest` would
  PANIC the Assert at line 490. [verified-by-code]
- Cycle-counter semantics: an entry with `cycle_ctr == sync_cycle_ctr`
  is "new since this drain started" and *not* processed in the
  current drain. Wraparound is bounded by the `sync_in_progress`
  recovery path. (lines 322–354)
- `data_sync_elevel(ERROR)` (used by md.c on fsync failure) escalates
  to PANIC if `data_sync_retry == false`, the default — the
  PostgreSQL "fsync errors are fatal" policy.
  `[from-comment]` (referenced in md.c, defined in fd.c)

## Cross-refs

- Outbound: `mdsyncfiletag` (md.c), `clogsyncfiletag`,
  `committssyncfiletag`, `multixactoffsetssyncfiletag`,
  `multixactmemberssyncfiletag` (their respective subsystems);
  `AbsorbSyncRequests`, `ForwardSyncRequest` (bgwriter.c /
  checkpointer.c).
- Inbound: md.c (every dirty-segment write), CLOG / multixact /
  commit_ts subsystems, `dropdb`.

## Open questions

- The shared-memory queue between regular backends and the
  checkpointer (`ForwardSyncRequest` / `AbsorbSyncRequests`) lives
  in `checkpointer.c`; I did not read that here. `[unverified]`
- The full wraparound argument relies on "we'd notice before
  CycleCtr (uint16) wraps in the wild" — true in practice but
  bounded only by the `sync_in_progress` recovery. `[from-comment]`

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 6 / `[unverified]` 2.
