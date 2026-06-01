# `src/backend/storage/smgr/md.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 2092
- **Source:** `source/src/backend/storage/smgr/md.c`

## Purpose

The "magnetic-disk" (md) storage manager: the only smgr implementation
PG ships. Despite the name it just maps the smgr API onto kernel
filesystem calls via fd.c VFDs. Two load-bearing tricks live here:
(1) breaking each fork into RELSEG_SIZE-block "segment" files so that
relations larger than the host's max file size work, and (2) the
fsync-by-checkpointer protocol via the sync request queue.
[from-comment] (`md.c:1-20`, `45-90`)

## Top of file

Lines 45–90 describe the on-disk layout invariant: a fork consists of
zero or more *full* segments of exactly RELSEG_SIZE blocks, exactly one
*partial* segment, optionally any number of *inactive* (zero-length)
segments left over from a truncate. Inactive segments are kept around
so that other backends/checkpointer that may still hold an fd into them
won't write into a unlinked-and-recreated file. This is the central
"why segments are weird" comment in PG storage.
[from-comment] (`md.c:55-69`)

## Public surface (md.h)

Functions called via the `smgrsw[]` vtable: `mdinit`, `mdopen`,
`mdclose`, `mdcreate`, `mdexists`, `mdunlink`, `mdextend`,
`mdzeroextend`, `mdprefetch`, `mdmaxcombine`, `mdreadv`, `mdstartreadv`,
`mdwritev`, `mdwriteback`, `mdnblocks`, `mdtruncate`, `mdimmedsync`,
`mdregistersync`, `mdfd`. Plus the sync handler callbacks:
`mdsyncfiletag`, `mdunlinkfiletag`, `mdfiletagmatches`. Plus admin
helpers: `ForgetDatabaseSyncRequests`, `DropRelationFiles`. Plus the
AIO completion callback table `aio_md_readv_cb`.

## Types of note

- `MdfdVec` (lines 92–96): one fd.c File handle + a segment number;
  per-fork array hung off `SMgrRelation.md_seg_fds[fork]` with
  `md_num_open_segs[fork]`.
- `FileTag` (defined in `sync.h`): identifies a fork+segment via
  handler/forknum/rlocator/segno — the unit that sync.c hashes for
  pending fsyncs.
- `MdCxt` (line 98): MemoryContext (AllocSet, child of
  TopMemoryContext) owning all `MdfdVec` arrays.

## EXTENSION_* behavior flags

`md.c:114-122` defines the `_mdfd_getseg()` policy bitmask:
`EXTENSION_FAIL`, `EXTENSION_RETURN_NULL`, `EXTENSION_CREATE`,
`EXTENSION_CREATE_RECOVERY`, `EXTENSION_DONT_OPEN`. The combination
chosen at each call site encodes the "what should happen if the segment
isn't there?" decision.

## Functions of note (the load-bearing ones)

**`_mdfd_getseg` (lines 1754–1878)** — the segment-finder. Given a
block number, returns the `MdfdVec` for the containing segment, opening
or creating intervening segments as needed. Key invariants:
- Segments are opened strictly in order; `_mdfd_openseg` asserts
  `segno == md_num_open_segs[forknum]`. [verified-by-code] (`md.c:1731`)
- When extending in recovery or via `EXTENSION_CREATE`, if the prior
  segment is < RELSEG_SIZE, it is *padded with zeros* to maintain the
  "all-but-last full" invariant. [verified-by-code]
  (`md.c:1810-1833`). This is the bit that exists because WAL replay
  can write into a high-numbered segment without having extended in
  order.
- When *not* extending and the prior segment isn't full, that's an
  error or NULL return — the caller is asking for a block past EOF.
  (`md.c:1836-1860`)

**`mdreadv` (lines 858–991)** — synchronous vectored read. Builds an
iovec from caller's buffer array via `buffers_to_iovec` (merges
contiguous physical buffers), short-read loops, EOF handling. The EOF
branch (lines 925–973) is in active deprecation: the
`zero_damaged_pages`/InRecovery code is now `Assert(false)` and slated
to be removed (PG 18 comment, `md.c:950-953`). Read crossing a
segment boundary is `elog(ERROR)`; callers must split via
`mdmaxcombine`. (`md.c:885-886`)

**`mdstartreadv` (lines 996–1061)** — AIO version. Sets up the iovec
and target into the `PgAioHandle`, registers the completion callback
`md_readv_complete`, calls `FileStartReadV` which kicks off the IO.
Note that the deprecated zero-on-EOF logic is intentionally *not*
duplicated here (md.c:1050-1060).

**`mdwritev` (lines 1070–1166)** — vectored write, mirrors mdreadv.
On success, if !skipFsync and not temp, calls `register_dirty_segment`
to enqueue a SYNC_REQUEST.

**`mdextend` (lines 487–544)** — single-block extend; uses
`FileWrite` at the computed seek position with EXTENSION_CREATE.

**`mdzeroextend` (lines 552–663)** — multi-block extend filled with
zeros. Above an 8-block cutoff uses `FileFallocate` (posix_fallocate)
to avoid forcing kernel page-cache allocation; below it falls back to
`FileZero` (pwritev of zeros). [verified-by-code] (`md.c:606-653`)

**`mdunlink` / `mdunlinkfork` (lines 337–476)** — the multi-step
"truncate-then-unlink, but keep the first segment until next
checkpoint" dance. The 30-line comment (`md.c:276-336`) explains *why*:
relfilenumber recycle hazard combined with `wal_level=minimal`
truncate-instead-of-WAL semantics. For the first segment of a
non-temp/non-upgrade main fork, it truncates (so disk space is
reclaimed) and queues a `SYNC_UNLINK_REQUEST` for the checkpointer;
additional segments are unlinked immediately. [from-comment]

**`mdtruncate` (lines 1301–1385)** — Guaranteed-no-allocation truncate
(must run in a critical section). Walks segments back-to-front:
inactive segments truncated to 0 and closed (but file kept); the
last-keep segment truncated to its new size. Segment 0 is *never*
dropped (`md.c:1349-1350`). [verified-by-code]

**`mdnblocks` (lines 1234–1286)** — reports total block count by
walking active segments from the last-opened one forward, stopping at
the first segment whose size is < RELSEG_SIZE. Side effect: opens all
unopened active segments and populates them in `md_seg_fds`.
[from-comment] (`md.c:1228-1232`)

**`register_dirty_segment` (lines 1518–1557)** — the fsync hand-off.
Builds a FileTag, tries `RegisterSyncRequest(SYNC_REQUEST,
retryOnError=false)`. If the queue is full, falls back to issuing the
`FileSync` synchronously *here* — that's the "we hope this doesn't
happen often" path. [verified-by-code]

**`mdsyncfiletag` (lines 1904–1948)** — called by the checkpointer
(via sync.c) to actually fsync a tagged segment. Opens the file if not
already in md's per-backend cache; closes it again if it opened it.

**`mdfd` (lines 1494–1507)** — return the raw kernel fd + intra-seg
offset; only used by AIO when the IO must execute in a different
process than the one that issued it.

## Invariants

- The fork's segment array contains entries only for currently-open
  segments; the first partial segment is treated as the end and any
  later entries are presumed inactive (no entry kept). [from-comment]
  (`md.c:79-90`)
- Segments are opened in monotonically increasing order of segno;
  enforced by assertion. [verified-by-code] (`md.c:1731`)
- `_fdvec_resize` (lines 1644–1685) *never shrinks* the array because
  `mdtruncate` promises to allocate no memory — a smaller-than-current
  request just records the new `md_num_open_segs` and leaves the
  trailing slot unused. [from-comment] (`md.c:1673-1681`)
- Read crossing a segment boundary is an error (`md.c:886, 1020`).

## Cross-refs

- Calls into `fd.c`: `PathNameOpenFile`, `FileClose`, `FileReadV`,
  `FileWriteV`, `FileWrite`, `FileSync`, `FileTruncate`,
  `FileFallocate`, `FileZero`, `FileWriteback`, `FilePrefetch`,
  `FileStartReadV`, `FileSize`, `FilePathName`.
- Calls into `sync.c`: `RegisterSyncRequest`.
- Called by `smgr.c` via the `smgrsw[]` vtable, and by `sync.c` via
  the `syncsw[SYNC_HANDLER_MD]` callbacks.

## Open questions

- The mdunlink → `register_unlink_segment` → SYNC_UNLINK_REQUEST →
  checkpoint flow: I traced the producer side here but the consumer
  side (sync.c's `SyncPostCheckpoint`) is in sync.c.md. The
  cycle-counter wraparound argument in sync.c is plausible but not
  fully checked here. `[unverified]`
- The AIO completion path's PARTIAL semantics (`md.c:2038-2044`) —
  "upper layer retries" — I haven't traced where that retry happens.
  `[unverified]`

## Tag tally

`[verified-by-code]` 8 / `[from-comment]` 7 / `[unverified]` 2.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
