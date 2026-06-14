# XLogReaderState — WAL record decoding

- **Source path:** `source/src/include/access/xlogreader.h`,
  `source/src/backend/access/transam/xlogreader.c`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Companion docs:** `knowledge/subsystems/access-transam.md`,
  `knowledge/subsystems/replication.md`,
  `knowledge/subsystems/contrib-pg_walinspect.md`,
  `.claude/skills/wal-and-xlog/SKILL.md`

## 1. What it is

A `XLogReaderState` is the **caller-side state machine for reading
and decoding WAL records**. The same struct backs recovery (replay
on a standby), `pg_waldump`, `contrib/pg_walinspect`, logical
decoding's reorderbuffer setup, and `pg_receivewal`. Reading WAL
from a backend goes through this surface.

The header is opaque — the public type is just `typedef struct
XLogReaderState XLogReaderState;`
[verified-by-code `xlogreader.h:56`]. The fields live in
`xlogreader.c`'s internal struct definition.

## 2. The flow

```c
/* 1. Allocate. */
state = XLogReaderAllocate(wal_segment_size, waldir, &routine,
                           caller_private);

/* 2. Position. */
XLogBeginRead(state, start_lsn);                 // exact LSN
/* OR */
XLogFindNextRecord(state, near_lsn);             // round up to next record

/* 3. Read in a loop. */
while ((record = XLogReadRecord(state, &errormsg)) != NULL) {
    /* DecodedXLogRecord lives at state->record (and *record). */
    rmid = XLogRecGetRmid(record);
    info = XLogRecGetInfo(record);
    /* Decoded blocks: XLogRecHasBlockRef, XLogRecGetBlockTag, ... */
}
if (errormsg) {
    /* end-of-WAL or read error */
}

/* 4. Free. */
XLogReaderFree(state);
```

[verified-by-code `xlogreader.h:11-31` (header docstring with
the same flow narrative)]

## 3. The callback surface — `XLogReaderRoutine`

The reader doesn't know how to find WAL bytes — the caller plugs in
three callbacks:

```c
typedef struct XLogReaderRoutine {
    XLogPageReadCB    page_read;        // get bytes for a page
    WALSegmentOpenCB  segment_open;     // open the next WAL segment file
    WALSegmentCloseCB segment_close;    // close on switch
} XLogReaderRoutine;
```

[verified-by-code `xlogreader.h:72-79`]

| Callback | Job |
|---|---|
| `page_read` | Read at least `reqLen` bytes of the WAL page at `targetPagePtr` into `readBuf`. Return bytes read, or -1 on failure. May sleep waiting for WAL to arrive (recovery / streaming). |
| `segment_open` | Open the WAL segment file containing `nextSegNo`; fill in the timeline. |
| `segment_close` | Close the currently-open segment. **Always supplied.** |

Helper: **`WALRead`** is a ready-made `page_read` implementation that
reads from `$PGDATA/pg_wal/` on disk; callers can use it directly or
write their own (e.g. streaming replication's walreceiver does its
own buffering).

## 4. Per-call output — decoded record

`XLogReadRecord` returns a `XLogRecord *` pointing into the reader's
internal buffer (do NOT free it; do NOT use it after the next read).
The decoded version is at `state->record`, a `DecodedXLogRecord` with:

| Field | Use |
|---|---|
| `header` | The on-disk record header (rmid, length, info byte, ...) |
| `lsn` | This record's start LSN |
| `next_lsn` | The next record's start LSN |
| `record_origin` | Replication origin (for logical decoding) |
| `main_data`, `main_data_len` | The rmgr-specific main payload |
| `blocks[]` | Per-block decoded `DecodedBkpBlock` entries |
| `max_block_id` | Highest valid `blocks[]` index |

Per-block accessors are macros / inlines:

- `XLogRecHasBlockRef(record, block_id)` — was this block referenced?
- `XLogRecGetBlockTag(record, block_id, &rlocator, &forknum, &blknum)`
  — locate the block in storage.
- `XLogRecHasBlockImage(record, block_id)` — is there an FPI (Full
  Page Image)?
- `XLogRecGetBlockData(record, block_id, &len)` — get the rmgr-specific
  per-block payload.

[verified-by-code `xlogreader.h` decoded-record section + macros]

## 5. The "decode without I/O" path

`DecodeXLogRecord(state, record, errormsg)` decodes a record that's
**already in memory** (not read from disk). Used by:

- The walsender — already has the bytes in shmem.
- Test code that synthesizes WAL records.
- The XLOG reader's own callers that buffer the bytes themselves.

This bypasses the page-read callback entirely. The decoded fields
are filled in `state->record` as if `XLogReadRecord` had run.

## 6. Position invariants

- **`state->ReadRecPtr`** — LSN of the most recently read record.
- **`state->EndRecPtr`** — first byte past the most recently read
  record (i.e. where the next record begins).
- **`state->currRecPtr`** — current read position; advances after
  each call.

The trio is maintained by the reader; consumers should treat them
as read-only. To re-seek, call `XLogBeginRead` again with the new
start LSN.

## 7. Error handling

- `XLogReadRecord` returns `NULL` AND sets `*errormsg` to a static
  string when the read fails (end-of-WAL, corrupt record, page-read
  callback returned -1).
- It does **not** `ereport(ERROR, ...)`. Caller is expected to
  check the return value and decide what level to emit at. This is
  critical for redo, which must `ereport(PANIC, ...)` on a corrupt
  WAL record, not `ERROR`.
- The `errormsg` string is in a fixed buffer inside the state and
  may be overwritten on the next call.

## 8. Invariants

- **[INV-1]** `segment_close` callback is mandatory; the other two
  are conditionally mandatory.
- **[INV-2]** The returned `XLogRecord *` is valid only until the
  next `XLogReadRecord` call — copy out anything you want to keep.
- **[INV-3]** The reader does NOT call `ereport(ERROR, ...)`.
  Callers must escalate based on context (PANIC in redo, ERROR /
  WARNING elsewhere).
- **[INV-4]** `state` is **not thread-safe** and is not designed
  to be shared across backends. Each backend / worker has its own
  state.
- **[INV-5]** `XLogReaderAllocate` may return `NULL` on OOM
  (because the WAL reader is used in frontend tools too where
  `palloc` isn't available); always check.

## 9. Common usage sites

| Site | Purpose |
|---|---|
| `xlog.c` (`StartupXLOG`) | Recovery / crash recovery |
| `walsender.c` | Stream WAL to standbys / logical-decoding clients |
| `pg_waldump.c` | Frontend CLI WAL inspection |
| `contrib/pg_walinspect/` | SQL surface for WAL inspection |
| `contrib/pg_receivewal/` | Persistent WAL receiver |
| `logical/decode.c` | Logical decoding plumbing |
| `pg_rewind` | LSN-bounded WAL replay simulation |

## 10. Useful greps

- All XLogReaderAllocate sites:
  `grep -RIn 'XLogReaderAllocate' source/src source/contrib`
- All custom page_read callbacks:
  `grep -RIn 'XLogPageReadCB\|page_read' source/src source/contrib`
- Per-block-id helpers:
  `grep -n 'XLogRecHasBlockRef\|XLogRecGetBlockTag\|XLogRecGetBlockData' source/src/include/access/xlogreader.h`

## Cross-references

- `.claude/skills/wal-and-xlog/SKILL.md` — XLogInsert (writer) is the counterpart; rmgr design.
- `.claude/skills/replication-overview/SKILL.md` — walsender / walreceiver use XLogReaderState.
- `knowledge/subsystems/access-transam.md` — surrounding xact / xid / xlog plumbing.
- `knowledge/subsystems/replication.md` — physical + logical streaming consumers.
- `knowledge/subsystems/contrib-pg_walinspect.md` — SQL surface using this struct.
- `source/src/backend/access/transam/xlogreader.c` — the implementation.
