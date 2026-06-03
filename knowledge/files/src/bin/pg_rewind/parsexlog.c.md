# parsexlog.c

## Purpose

Drives `XLogReader` from frontend code to:

1. Walk the target's WAL forward from the last common checkpoint
   (`extractPageMap`) and accumulate, per relfile, the set of dirty
   blocks (the `datapagemap_t`s) — these are the blocks that must be
   copied from the source to undo the target's divergent work.
2. Read a single WAL record at a given LSN (`readOneRecord`).
3. Walk WAL **backwards** from a given LSN to find the most recent
   checkpoint record (`findLastCheckpoint`).

It plugs the frontend page-read callback `SimpleXLogPageRead` into
`XLogReader`, which handles missing segments by either failing or
calling out to `RestoreArchivedFile` if a `restore_command` was given.

## Role in pg_rewind

This is the "what changed on the target" engine. The top-level flow in
`pg_rewind.c`:

1. Find divergence LSN by comparing target & source timeline histories.
2. `findLastCheckpoint(target, divergeLSN, ...)` — walk target WAL
   backwards from divergence to the previous checkpoint.
3. `extractPageMap(target, last_chkpt, ..., divergeLSN, ...)` — walk
   target WAL forward from the checkpoint to divergence, recording
   every dirty block in the filemap.
4. Pages in the resulting map are fetched from the source in the copy
   phase.

`readOneRecord` is used for sanity checks (e.g. confirming the LSN of
a checkpoint record).

## Key functions

- `extractPageMap(datadir, startpoint, tliIndex, endpoint, restoreCommand)`
  (`source/src/bin/pg_rewind/parsexlog.c:65-117`). Allocates an
  `XLogReader` rooted at `datadir/pg_wal`, `XLogBeginRead(start)`, then
  loops `XLogReadRecord` → `extractPageInfo` until `EndRecPtr >= endpoint`.
  Any unreadable record is fatal. `endpoint` must land exactly on a record
  boundary — otherwise fatal "end pointer ... is not a valid end point".
- `readOneRecord(...)` (`:123-162`). Same setup, but reads exactly one
  record and returns its `EndRecPtr`.
- `findLastCheckpoint(...)` (`:167-271`). Walks backwards via the
  `xl_prev` field on each record. For each segment crossed, calls
  `keepwal_add_entry(xlogfname)` so the segment isn't removed by the
  later cleanup pass. Stops when it finds an `XLOG_CHECKPOINT_SHUTDOWN`
  or `XLOG_CHECKPOINT_ONLINE` record at LSN < `forkptr` (`:247-259`),
  reading the embedded `CheckPoint` struct via `memcpy`. The
  initial `forkptr` adjustment at `:187-193` skips an XLOG page header
  if `forkptr` lands at page start.
- `SimpleXLogPageRead(xlogreader, targetPagePtr, reqLen, targetRecPtr,
  readBuf)` (`:274-383`). XLogReader's page-read callback. Closes the
  open segment if the request crosses into a new one, opens the right
  file based on `targetHistory[tliIndex]`, falls back to
  `RestoreArchivedFile()` if the local segment is missing and a
  `restore_command` was provided. Adjusts `tliIndex` forward/backward
  based on segment-end vs timeline `begin/end` bounds.
- `extractPageInfo(record)` (`:388-483`). The classifier. Switches on
  `rmid` / `rminfo`:
  - `RM_DBASE_ID` create/drop, `RM_SMGR_ID` create/truncate, `RM_XACT_ID`
    commit/abort → safe to ignore (file-level changes that the filemap
    layer handles separately).
  - `info & XLR_SPECIAL_REL_UPDATE` for any other rmgr → fatal "WAL
    record modifies a relation, but record type is not recognized".
  - Otherwise: iterate `block_id` 0..`XLogRecMaxBlockId`, call
    `XLogRecGetBlockTagExtended`, and for `MAIN_FORKNUM` blocks call
    `process_target_wal_block_change(forknum, rlocator, blkno)` which
    inserts into the relevant `datapagemap_t`.

## State / globals

- `static int xlogreadfd = -1`, `static XLogSegNo xlogreadsegno = 0`,
  `static char xlogfpath[MAXPGPATH]` (`:43-45`). Cache of the currently
  open WAL segment. `extractPageMap` / `readOneRecord` /
  `findLastCheckpoint` each close this fd before returning.
- `targetHistory[]`, `targetNentries` (from `pg_rewind.h`) — the parsed
  timeline history of the target, indexed by `XLogPageReadPrivate.tliIndex`.
- `RmgrNames[RM_MAX_ID + 1]` (`:34-36`) — built from `rmgrlist.h`.
  Used only for nicer error messages.

## Phase D notes

### WAL trust posture

The WAL being parsed here is the **target's** local pg_wal directory.
There is no remote attacker to worry about — if WAL on the target's
disk is malicious, the target is already compromised. However:

- **`memcpy(&checkPoint, XLogRecGetData(xlogreader), sizeof(CheckPoint))`**
  at `:254` trusts that the checkpoint record's payload is at least
  `sizeof(CheckPoint)` bytes. There is no length check. If a corrupt
  WAL contained a truncated checkpoint record, the memcpy reads past
  the record's `xl_tot_len` boundary. In practice `XLogReadRecord`
  is supposed to have validated `xl_tot_len`, so the buffer should be
  large enough — but `extractPageInfo` already had a fatal-on-unknown
  branch (`:461-465`) showing the file is defensive elsewhere.
- **`pg_fatal` on any read error.** This is correct (don't silently
  produce a wrong filemap) but means any single corrupt WAL byte
  bricks the rewind. There's no "skip and continue" fallback.
- **No length check on block-id loop** — `XLogRecMaxBlockId` is
  capped by `XLogReader` itself (`XLR_MAX_BLOCK_ID = 32`), so the
  loop in `extractPageInfo` is bounded.
- **No decompression here.** WAL records may contain compressed FPIs,
  but `XLogReader` (in `src/backend/access/transam/`) handles
  decompression internally; `extractPageInfo` only consumes
  `XLogRecGetBlockTag*` metadata, not page payloads. So
  decompression-bomb / oversized-FPI attacks would land in
  XLogReader, not here.

### Anything weird in parsexlog.c's WAL trust posture?

Two things stand out:

1. **`SimpleXLogPageRead` opens WAL segments with plain `open()` —
   no `O_NOFOLLOW`** (`:324`). If a malicious tenant on the target
   has planted a symlink at `<datadir>/pg_wal/<segname>` pointing to
   `/etc/passwd`, the read will silently use that file as a WAL
   segment. `XLogReadRecord` will reject it as invalid, so impact
   is limited to "wrong file consumed once" — but the symlink dance
   leaves no audit trail.
2. **`RestoreArchivedFile`** (`:341-344`) executes `restore_command`
   via a shell. The command is operator-supplied (passed via
   `-c restore_command=...`), so not a Phase D issue per se — but
   it's a place where pg_rewind reaches outside its own process and
   trusts the operator's shell snippet to behave.

### Forward vs backward scan in findLastCheckpoint

`findLastCheckpoint` walks backwards via `record->xl_prev`. Each
backward step requires the previous segment to still exist. Hence
the `keepwal_add_entry` calls (`:238`) — pg_rewind's later cleanup
pass would otherwise delete those segments. This is also why pg_rewind
sometimes errors out with "could not find previous WAL record" on
operators who've aggressively truncated WAL.

## Potential issues

- `[ISSUE-trust-boundary: SimpleXLogPageRead opens WAL segments
  without O_NOFOLLOW (low)]` (`:324`). A symlinked WAL file is
  followed silently. Limited blast radius since XLogReader will
  reject non-WAL content, but a hardening gap.
- `[ISSUE-correctness: checkpoint record payload memcpy lacks an
  explicit length check (maybe)]` (`:254`). Relies on XLogReader's
  upstream length validation. If a future XLogReader change relaxes
  that, this site silently reads OOB. A `Assert(XLogRecGetDataLen(record)
  >= sizeof(CheckPoint))` would future-proof.
- `[ISSUE-state-transition: any unrecognized WAL record with
  XLR_SPECIAL_REL_UPDATE fatals the entire rewind (low)]`
  (`:454-465`). This is the correct, conservative behaviour — but
  it means pg_rewind silently regresses if a future PG version adds
  a new XLR_SPECIAL_REL_UPDATE rmgr op and the operator runs a
  too-old pg_rewind. Documented [from-comment].
- `[ISSUE-stale-todo: "consider also switching timeline accordingly"
  in SimpleXLogPageRead (low)]` (`:309-310`). Phrasing suggests the
  forward/backward timeline-walk logic might be incomplete in some
  edge case. No bug evident but the comment is unsure.
- `[ISSUE-dos: pg_fatal-on-first-bad-record gives no diagnostic
  surface (low)]` (`:91-97`). For operator debugging it would be
  nicer to dump the partial filemap before exiting. Cosmetic.
