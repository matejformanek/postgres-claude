# WAL (Write-Ahead Log) — architectural overview

Scope: conceptual reference for the WAL subsystem (also called XLOG in the code).
Companion docs: `mvcc.md`. Operational checklist for adding WAL records:
`.claude/skills/wal-and-xlog/SKILL.md`. Deep file-level walk of
`access/transam/*.c` is deferred until that subsystem is documented in
`knowledge/subsystems/`.

Source anchor: `source/src/backend/access/transam/README` (read end to end —
the "Write-Ahead Log Coding" section is canonical).

## 1. Why WAL exists

The fundamental rule: **log records describing a page change must reach stable
storage before the changed page itself does.** This is the "write-ahead" part.
[from-README `source/src/backend/access/transam/README:407-415`]

Consequences:
- Replaying the log from the last checkpoint forward brings the cluster to a
  consistent state, with no partially-performed transactions. [from-README
  `transam/README:407-411`]
- Each shared-buffer page carries an **LSN** (Log Sequence Number) — the WAL
  position of the most recent record affecting that page. Before bufmgr can
  write a dirty page out, it must flush WAL at least up to that LSN.
  [from-README `transam/README:411-415`]
- The LSN check lives only in the *shared* buffer manager, not the local buffer
  manager for temp tables. Hence **temp table changes are never WAL-logged**.
  [from-README `transam/README:416-418`; see also `transam/README:876-878`]

## 2. LSN (Log Sequence Number)

- Type: `XLogRecPtr` — a 64-bit byte offset into the conceptually-infinite WAL
  stream. [verified-by-code `source/src/include/access/xlogdefs.h`
  (referenced from `xlogrecord.h:16`)]
- A page's LSN is set with `PageSetLSN()` *after* `XLogInsert()` returns the
  record's position. [from-README `transam/README:457-466`]
- During replay, a record whose LSN ≤ page LSN has already been applied — its
  redo can be skipped. [from-README `transam/README:420-422`]
- LSN read/write rules: only the startup process may modify pages during
  recovery, so it can call `PageGetLSN` unlocked. Other processes need either
  exclusive content lock, or shared + buffer header lock, to call
  `PageSet/GetLSN` safely. [from-README `transam/README:620-626`]

## 3. WAL record structure

Layout, in order: [verified-by-code
`source/src/include/access/xlogrecord.h:20-40`]

```
[ XLogRecord                 ]   fixed header
[ XLogRecordBlockHeader  * N ]   one per buffer referenced (0..XLR_MAX_BLOCK_ID=32)
[ XLogRecordDataHeader      ]   short (<256B) or long form for "main data"
[ block data * N            ]   per-block payload (omitted if full-page image taken)
[ main data                 ]   rmgr-specific
```

`XLogRecord` fixed header [verified-by-code `xlogrecord.h:41-55`]:

| field | meaning |
|---|---|
| `xl_tot_len` | total record length |
| `xl_xid` | inserting xact ID |
| `xl_prev` | XLogRecPtr of previous record (back-link, for scanning) |
| `xl_info` | low 4 bits: XLR_* flags; high 4 bits: rmgr-private |
| `xl_rmid` | resource manager ID (selects redo function) |
| `xl_crc` | CRC32C over the whole record |

Per-block reference (`XLogRecordBlockHeader` + optional
`XLogRecordBlockImageHeader`) carries: relfilelocator (or `BKPBLOCK_SAME_REL`
to inherit the previous), fork number, block number, optional **full-page
image** with hole-removal and optional compression (PGLZ / LZ4 / ZSTD).
[verified-by-code `xlogrecord.h:103-167`]

Max record size: `XLogRecordMaxSize = 1020 MiB` (driven by `MaxAllocSize`
constraint on the reader). [verified-by-code `xlogrecord.h:74`]

Reserved block-ID sentinels: `255` short data, `254` long data, `253` replication
origin, `252` top-level XID for logical decoding. [verified-by-code
`xlogrecord.h:241-246`]

## 4. Constructing a WAL record — the XLogInsert API

The standard idiom is documented in
`source/src/backend/access/transam/README:489-528`. Public API in
`source/src/include/access/xloginsert.h:44-65`:

```c
XLogBeginInsert();
XLogRegisterBuffer(0, buf, REGBUF_STANDARD);  /* one call per modified buffer */
XLogRegisterData(&xlrec, SizeOfFoo);          /* "main data" */
XLogRegisterBufData(0, payload, len);         /* per-block data; dropped if FPI taken */
recptr = XLogInsert(RM_FOO_ID, XLOG_FOO_INFO);
PageSetLSN(page, recptr);
```

`REGBUF_*` flags [verified-by-code `xloginsert.h:31-41`]:
- `REGBUF_FORCE_IMAGE` — always include a full-page image (FPI).
- `REGBUF_NO_IMAGE` — never include one (use only when torn-page risk is moot).
- `REGBUF_WILL_INIT` — redo will re-init the page from scratch; implies NO_IMAGE
  but still protects against torn pages because the page is rebuilt.
- `REGBUF_STANDARD` — standard page layout; the unused "hole" between
  `pd_lower` and `pd_upper` is excluded from the FPI to shrink WAL.
- `REGBUF_KEEP_DATA` — include registered block data even when an FPI is taken.

Default working-area limits: 5 block references and 20 data chunks. Raise via
`XLogEnsureRecordSpace()` *before* `XLogBeginInsert()` and *outside* the
critical section. [from-README `transam/README:542-553`]

## 5. The five-step write rule (critical sections)

The schema for any WAL-logged page modification is fixed and must be obeyed
exactly: [from-README `transam/README:437-470`]

1. Pin & exclusive-lock the buffer(s).
2. `START_CRIT_SECTION()` — any error from here on is a `PANIC`.
3. Apply the in-memory page changes.
4. `MarkBufferDirty()` — **must** happen before the WAL insert; see
   `SyncOneBuffer` for why. [from-README `transam/README:450-453`]
5. `XLogBeginInsert` / `XLogRegister*` / `recptr = XLogInsert(...)`;
   `PageSetLSN(page, recptr)`.
6. `END_CRIT_SECTION()`.
7. Unlock & unpin.

The critical section guarantees: between step 3 and step 5 the buffer holds
unlogged changes; an error before the WAL insert completes would risk those
changes reaching disk via a later flush, so we PANIC instead of trying to
recover. [from-README `transam/README:441-446`]

Complex multi-page actions are split into a sequence of self-consistent WAL
records, each individually atomic; intermediate states must be sane because
replay can be interrupted at any point. [from-README `transam/README:471-486`]
The btree page-split is the worked example (parent insertion flagged
`incomplete_split`, cleared by the second record).

## 6. Full-page writes (FPI / FPW)

If the OS/hardware can tear page writes, a partial page on disk would defeat
incremental redo. To repair this, the **first WAL record touching a given page
after a checkpoint contains a copy of the whole page** (the FPI). Redo applies
the image instead of the incremental delta. The trigger is whether the page's
old LSN precedes the checkpoint's `RedoRecPtr`. [from-README
`transam/README:427-435`; verified-by-code `xlogrecord.h:117-167`]

GUC: `full_page_writes` (default on). The hole between `pd_lower` and
`pd_upper` of standard pages is stripped from the image; with
`wal_compression` (`pglz` / `lz4` / `zstd`), the remainder may be compressed.
[verified-by-code `xlogrecord.h:128-167`, `xlog.c:131`]

There is also a special `XLOG_FPI_FOR_HINT` record emitted when
`MarkBufferDirtyHint()` dirties a clean page with checksums or
`wal_log_hints` enabled — protecting hint-bit-only writes against torn pages.
[from-README `transam/README:638-645`]

## 7. Checkpoints

A checkpoint flushes all dirty shared buffers to disk and writes a
`CHECKPOINT` WAL record. After a successful checkpoint, redo can start no
earlier than `RedoRecPtr` (the WAL position at which the checkpoint *began*,
not where it ended). [inferred from `transam/README:430-435` discussion of
"end of WAL as of the last checkpoint"]

Triggers (GUCs in `xlog.c`): [verified-by-code
`source/src/backend/access/transam/xlog.c:121-143`]
- `max_wal_size` (soft target; default 1 GB) — drives the volume-based
  checkpoint cadence.
- `min_wal_size` (default 80 MB) — preallocation floor.
- `checkpoint_timeout` (time-based trigger; in `checkpointer.c`,
  not shown here). [unverified location, but standard GUC]
- `wal_keep_size`, `max_slot_wal_keep_size` — retention floors for
  replication.

After a crash, `StartupXLOG()` (`xlog.c:18-20`) replays from the last
checkpoint's redo pointer to the end of WAL, then transitions to normal
operation. [verified-by-code `xlog.c:14-20`]

## 8. Flushing and durability

- `XLogFlush(lsn)` — sync WAL out to at least `lsn`. Called by bufmgr before
  evicting a dirty page, and by transaction commit. [from-comment `xlog.c:22-25`]
- `XLogBackgroundFlush()` — walwriter's periodic flush; advances the flush
  pointer in whole-page chunks under load. [from-README `transam/README:796-813`]
- `wal_sync_method` GUC — `fsync` / `fdatasync` / `open_sync` / `open_datasync`
  / `fsync_writethrough` (platform-dependent). [verified-by-code
  `xlog.c:178-191`]

### Asynchronous commit

With `synchronous_commit = off`, commit does **not** wait for the commit
record's flush; the LSN is recorded in shared memory and the walwriter
catches up within at most ~3× `wal_writer_delay`. [from-README
`transam/README:780-813`]

- Abort records are *never* flushed synchronously: after a crash we assume any
  unflushed xact aborted anyway. [from-README `transam/README:784-787`]
- DDL with non-rollbackable filesystem side effects forces sync commit.
  [from-README `transam/README:789-794`]
- The clog-page-LSN trick: for each clog page we store the LSN of the latest
  async commit on that page, so we cannot write the clog page out before its
  WAL has flushed; otherwise a hint-bit-setting visibility check could leak
  the commit to a relation page before the commit record is durable.
  [from-README `transam/README:815-841`]

## 9. wal_level

Enum in `xlog.h:76-78` [verified-by-code]:

| level | what it logs | enables |
|---|---|---|
| `minimal` | only what's needed for crash recovery | nothing else |
| `replica` (default) | + info for archiving and physical replication / hot standby | PITR, streaming standbys, hot standby reads |
| `logical` | + extra metadata for logical decoding | logical replication, decoding plugins |

[verified-by-code `xlog.h:76-78`, default `WAL_LEVEL_REPLICA` at `xlog.c:138`]

`XLogIsNeeded() := wal_level >= replica` gates WAL emission for cases the
crash-recovery path doesn't strictly need. [verified-by-code `xlog.h:112`]

### Skipping WAL under `wal_level=minimal`

If a change targets a relfilenumber that ROLLBACK would unlink anyway
(typical: CREATE/REWRITE in the same xact), in-tree access methods skip the
WAL entirely; `CommitTransaction()` writes and fsyncs the affected blocks
before recording the commit. [from-README `transam/README:746-775`] This is
`RelationNeedsWAL()` — custom access methods must respect it or explicitly
opt out via `FlushRelationBuffers()` + `smgrimmedsync()`, or by always
WAL-logging unconditionally.

## 10. Archive vs streaming — the same WAL, two transports

WAL has three downstream uses, all reading the same record stream:

1. **Crash recovery** — local startup replay. Always on.
2. **Archive / PITR** — `archive_mode = on/always` + `archive_command` /
   `archive_library` ship completed WAL segments to archival storage.
   [verified-by-code `xlog.c:126-127, 198-201`] Requires
   `wal_level >= replica`.
3. **Streaming replication** — walsenders pipe WAL live to walreceivers on
   standbys; standbys can be hot (queryable). Requires `wal_level >= replica`.

Recovery vs replication is the *same redo path* — the startup process loops on
"fetch next record, dispatch to its rmgr's `rm_redo`". The differences are
where records come from (local pg_wal vs restore_command vs walreceiver) and
whether the loop stops at a target or runs until the source stops.
[inferred from `xlog.c:11-20` and the rmgr structure]

## 11. Resource managers (rmgr)

The redo path is dispatched by `xl_rmid`. The dispatch table is
`RmgrTable[RM_MAX_ID + 1]`, built from `access/rmgrlist.h`. [verified-by-code
`source/src/backend/access/transam/rmgr.c:46-52`]

Each entry is an `RmgrData` with callbacks: [verified-by-code
`source/src/include/access/xlog_internal.h:351-362`]

| callback | role |
|---|---|
| `rm_redo` | replay a record |
| `rm_desc` | human-readable description (for pg_waldump) |
| `rm_identify` | short record name from `xl_info` |
| `rm_startup` / `rm_cleanup` | lifecycle hooks at recovery boundaries |
| `rm_mask` | mask out bits irrelevant for `wal_consistency_checking` |
| `rm_decode` | logical-decoding hook |

Built-in rmgr IDs: 0..127. Custom rmgr IDs: **128..255** (`RM_MIN_CUSTOM_ID`
.. `RM_MAX_CUSTOM_ID`); `RM_EXPERIMENTAL_ID = 128` is reserved for
development. [verified-by-code
`source/src/include/access/rmgr.h:33-60`]

Custom rmgr registration: `RegisterCustomRmgr(rmid, &rmgr)` must be called
from `_PG_init` while `process_shared_preload_libraries_in_progress` is true;
name and ID must be globally unique across loaded extensions.
[verified-by-code `rmgr.c:107-146`] The community maintains a global registry
at <https://wiki.postgresql.org/wiki/CustomWALResourceManagers>.
[from-comment `rmgr.c:100-104`]

### rmgrdesc and pg_waldump

`pg_waldump` walks the WAL stream and, for each record, calls
`rm_identify(info)` and `rm_desc(buf, record)` to print it. The desc
functions live in `src/backend/access/rmgrdesc/` and are shared with the
runtime so that custom rmgrs work in `pg_waldump` too. [from-README
`source/src/backend/access/rmgrdesc/README:1-16`]

Output format is roughly JSON-ish but not a stable API; conventions are
documented in `rmgrdesc/README:17-61` (key/value, top-level braces omitted,
nested `{}` for sub-objects, lengths before arrays).

## 12. Generic WAL — for extensions that just modify pages

`src/backend/access/transam/generic_xlog.c` provides a way to write WAL
without registering a custom rmgr. It computes a *delta* between the
pre-image and post-image of each modified page (fragments of
`<offset, length, data>`), and stores the delta. Replay applies the delta
forward. [verified-by-code `generic_xlog.c:21-44`]

Trade-offs:

- Pros: trivial integration; no rmgr ID to allocate; works in any extension.
- Cons: the WAL record is at most a page-delta size, but the *common* case
  (small targeted changes) is larger than a hand-rolled record could be;
  no logical decoding; no custom redo semantics. [inferred]

Use generic WAL for prototypes, small access methods, or any case where
record volume isn't a concern. Use a custom rmgr when you need compact
records, logical decoding, or fine-grained replay logic.

## 13. Two-phase commit (PREPARE TRANSACTION)

A prepared xact reserves a Global Transaction ID (GID) in a shared-memory
array. PREPARE writes a `TWOPHASE`-rmgr WAL record carrying the prepared
state; COMMIT PREPARED / ROLLBACK PREPARED then write further records.
[verified-by-code
`source/src/backend/access/transam/twophase.c:12-23`] Recovery rebuilds the
in-memory 2PC state from WAL plus on-disk `pg_twophase/` state files for any
prepared xacts that were not yet resolved at crash time. [inferred from
twophase.c top comment]

Prepared transactions show up in `procarray.c` as PGPROC entries with
`pid == 0`. [verified-by-code `procarray.c:17-20`]

## 14. Hint bits and torn pages

Some changes are *hints* — they optimise future visibility checks but can be
re-derived from authoritative state. The canonical example is the
`HEAP_XMIN_COMMITTED` / `HEAP_XMAX_COMMITTED` bits in tuple infomask, which
just cache the result of looking up the inserter/deleter in pg_xact.

Rules: [from-README `transam/README:629-665`]

- Use `MarkBufferDirtyHint()` (never `MarkBufferDirty()`) for a hint-only write.
- If the buffer is clean and **(checksums on || `wal_log_hints` on)**,
  `MarkBufferDirtyHint()` first emits an `XLOG_FPI_FOR_HINT` record so the
  next torn-page hazard is covered by an FPI.
- During recovery, no WAL is written, so hint-bit updates are skipped.

Special case: `PD_ALL_VISIBLE` is a hint about the page, but its *clearing*
is always treated as a durable change to keep the visibility-map invariant
(VM bit set ⇒ page has PD_ALL_VISIBLE). [from-README `transam/README:648-665`]

## 15. WAL for filesystem actions (file/dir create/drop)

The "WAL before the change" rule doesn't fit operations that can fail
mid-flight (file create, unlink, mkdir tree). Strategies, all from
`transam/README:666-742`:

| action | strategy |
|---|---|
| extend table | not WAL-logged; write zeroes, then a normal WAL-logged init |
| create file | do it; if it works, WAL it; orphans on crash are tolerable |
| drop file | WAL first; treat unlink failure as warning |
| create/drop dir tree | do it, then WAL; partial failure on drop = corrupt DB |

In all "do then WAL" cases, redo failure during recovery is `PANIC` — the DBA
must repair the filesystem and resume. [from-README `transam/README:738-742`]

## 16. Transaction emulation during recovery

Recovery doesn't run real transactions, but it must keep enough emulation
that hot-standby read backends can take MVCC snapshots: [from-README
`transam/README:887-913`]

- A list of in-flight XIDs is maintained from `RUNNING_XACTS` and per-record
  XIDs (see `KnownAssignedXids` in `procarray.c:25-30`).
- pg_xact / multixact / commit_ts are written normally; pg_subtrans is
  maintained but the tree is flattened (all subxacts reference the
  top-level XID).
- No lock table entries are added for in-flight xacts; lock waiters wait on
  the top-level xact.
- Subtransaction commit doesn't write WAL, so it's invisible in recovery.

## 17. Open questions and unverifieds

- `[unverified]` Exact relationship between `RedoRecPtr` and the
  `CHECKPOINT` record's own LSN — the README mentions "end of WAL as of the
  last checkpoint" but the precise pointer semantics need a code read in
  `CreateCheckPoint()` to confirm.
- `[unverified]` Behaviour of `wal_compression = on` vs the per-record
  compression flags in `BKPIMAGE_COMPRESS_*` when the chosen compressor is
  not built in (does it fall back, error, or silently store raw?).
- `[unverified]` Whether `checkpoint_timeout` is documented in `xlog.c` or
  elsewhere — it's a standard GUC but not visible in the file head we read.
- `[inferred]` "Recovery and replication share the same redo path" is a
  conceptual claim; the actual dispatch is in `xlogrecovery.c` which we did
  not read.
