# XLog region replay — the XLogReadBufferForRedo pattern

The redo function of every resource manager (rmgr) consumes WAL
records produced by its build-time counterpart. The redo
function's job is to re-apply changes deterministically — the
**same** record on a freshly-loaded buffer must produce the
**same** end state, even though the original modification
happened weeks or months ago on a different machine. The
canonical idiom is the `XLogReadBufferForRedo` + return-code
switch.

Anchors:
- `source/src/include/access/xlogutils.h:71-92` — the API +
  return codes [verified-by-code]
- `source/src/backend/access/transam/xlogutils.c` —
  implementation
- `source/src/backend/access/nbtree/nbtxlog.c` — canonical
  caller (B-tree redo)
- `knowledge/idioms/wal-record-construction.md` — companion:
  the write side

## The four return codes

```c
typedef enum
{
    BLK_NEEDS_REDO,    /* changes from WAL record need to be applied */
    BLK_DONE,          /* block is already up-to-date */
    BLK_RESTORED,      /* block was restored from a full-page image */
    BLK_NOTFOUND       /* block was not found */
} XLogRedoAction;
```

[verified-by-code `xlogutils.h:72-77`]

Each redo block-by-block decision falls into one of these four
buckets:

- **`BLK_NEEDS_REDO`** — the buffer page's LSN < the record's
  LSN. The redo function MUST apply the per-buffer-data
  payload to bring the page up to date.
- **`BLK_DONE`** — the page's LSN ≥ the record's LSN. The
  modification was already applied (probably during a previous
  crash recovery that didn't reach the consistent point). Redo
  function does NOT apply changes.
- **`BLK_RESTORED`** — the record carried a full-page image
  and `XLogReadBufferForRedo` already wrote it into the
  buffer. Redo function does NOT apply per-buffer-data
  (the FPI is the truth; the per-buffer-data is just a
  fallback).
- **`BLK_NOTFOUND`** — the relation doesn't exist anymore
  (e.g. DROP TABLE replayed earlier). Redo function should
  skip this block silently.

## The canonical caller pattern

```c
static void
btree_xlog_someop(XLogReaderState *record)
{
    XLogRecPtr  lsn = record->EndRecPtr;
    Buffer      buf;
    Page        page;

    if (XLogReadBufferForRedo(record, 0, &buf) == BLK_NEEDS_REDO)
    {
        page = (Page) BufferGetPage(buf);
        /* apply the modification using record->main_data ... */
        PageSetLSN(page, lsn);
        MarkBufferDirty(buf);
    }
    if (BufferIsValid(buf))
        UnlockReleaseBuffer(buf);
}
```

[canonical, verified-by-code `nbtxlog.c:142-180`]

The pattern is rigid:

1. Call `XLogReadBufferForRedo(record, block_id, &buf)`.
2. If `BLK_NEEDS_REDO`, apply changes + `PageSetLSN` +
   `MarkBufferDirty`.
3. Otherwise do nothing.
4. **Always** release the buffer if valid (`BLK_NOTFOUND`
   leaves buf invalid).

## The "init" variant

When the WAL record was produced with `REGBUF_WILL_INIT`, the
record carries no FPI and no incremental data — the redo
function is expected to fabricate the page from scratch.

```c
buf = XLogInitBufferForRedo(record, block_id);
page = BufferGetPage(buf);
PageInit(page, BLCKSZ, sizeof(BTPageOpaqueData));
/* fill in initial contents from record->main_data */
PageSetLSN(page, lsn);
MarkBufferDirty(buf);
UnlockReleaseBuffer(buf);
```

[verified-by-code via `xlogutils.h:89`]

No return-code check — `XLogInitBufferForRedo` always succeeds
or PANICs. Use only when the build-time emission used
`REGBUF_WILL_INIT`.

## The "extended" variant

`XLogReadBufferForRedoExtended` exposes the read-mode and
"get-cleanup-lock?" parameters explicitly. Use when:

- You need `RBM_ZERO_AND_LOCK` mode (caller initializes the
  buffer instead of reading from disk).
- You need an exclusive cleanup lock instead of an exclusive
  content lock (e.g. for VACUUM operations that delete tuples
  and must wait for all pinners to release).

The cleanup-lock flag must match the build-time emission's
expectation — running redo with the wrong lock mode = silent
corruption.

## The recovery LSN ordering

`record->EndRecPtr` is the LSN AT WHICH the record ends, i.e.
the LSN immediately after the record. Pages stamped with this
LSN are "as of after this record."

`record->ReadRecPtr` is the start LSN. Usually irrelevant for
redo — use `EndRecPtr`.

The PageSetLSN happens **after** the modification, never
before, so that a crash between modification and SetLSN can be
re-applied (the page LSN still < record LSN → BLK_NEEDS_REDO).

## Idempotence and determinism

Redo is **idempotent** — applying the same record twice to a
page that already has the LSN must produce the same final
state. The `BLK_DONE` return code is the mechanism: if the page
already shows this record's LSN, redo is a no-op.

Redo is **deterministic** — the same record on a page at the
same prior state MUST produce identical bytes. Any
non-determinism (e.g. reading the current time) breaks
replication.

## Common review-time concerns

- **Always check the return code before reading the buffer.**
  `BLK_NOTFOUND` leaves the buffer pointer invalid; using it
  is a use-after-free.
- **`PageSetLSN(page, record->EndRecPtr)` after the
  modification, before `MarkBufferDirty`.** Forgetting it
  means the WAL-before-data invariant breaks on the next
  checkpoint.
- **Don't read other resources in redo.** No catalog lookups,
  no allocations that depend on dynamic state, no clock reads.
  Redo runs against a database that may not be consistent yet.
- **`BLK_NOTFOUND` is normal during crash recovery** — a
  DROP TABLE replay drops the relation, then a later WAL
  record references its blocks. Silent skip is correct.

## Invariants

- **[INV-1]** Apply changes ONLY on `BLK_NEEDS_REDO`. Other
  return codes mean "don't apply."
- **[INV-2]** After `BLK_NEEDS_REDO` and the modification,
  set the page LSN and mark dirty.
- **[INV-3]** Redo MUST be idempotent and deterministic.
- **[INV-4]** Redo runs in a recovery process with limited
  catalog access; don't depend on dynamic database state.
- **[INV-5]** `XLogInitBufferForRedo` is for `REGBUF_WILL_INIT`
  records only; `XLogReadBufferForRedo` for the rest.

## Useful greps

- All rmgr redo entry points:
  `grep -RIn 'static void.*_redo\b' source/src/backend/access`
- BLK_* return-code consumers:
  `grep -RIn 'BLK_NEEDS_REDO\|BLK_DONE\|BLK_RESTORED\|BLK_NOTFOUND' source/src/backend/access | head -30`
- XLogInitBufferForRedo sites:
  `grep -RIn 'XLogInitBufferForRedo' source/src/backend/access`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/nbtree/nbtxlog.c`](../files/src/backend/access/nbtree/nbtxlog.c.md) | — | canonical per-AM redo function set |
| [`src/backend/access/transam/xlogutils.c`](../files/src/backend/access/transam/xlogutils.c.md) | — | implementation |
| [`src/include/access/xlogutils.h`](../files/src/include/access/xlogutils.h.md) | 71 | the API + return codes |
| [`src/include/access/xlogutils.h`](../files/src/include/access/xlogutils.h.md) | — | public API + return codes |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/wal-record-construction.md` — companion:
  the build-time emission this pattern consumes.
- `knowledge/idioms/crash-recovery-startup.md` — companion:
  the top-level recovery driver that calls each rmgr's redo.
- `knowledge/data-structures/xlogreaderstate.md` — the
  `XLogReaderState *record` parameter.
- `.claude/skills/wal-and-xlog/SKILL.md` — skill covering the
  WAL contract.
- `knowledge/subsystems/access-transam.md` — the xlog
  subsystem.
- `source/src/include/access/xlogutils.h` — public API + return
  codes.
- `source/src/backend/access/nbtree/nbtxlog.c` — canonical
  per-AM redo function set.
