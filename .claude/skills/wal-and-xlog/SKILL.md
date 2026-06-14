---
name: wal-and-xlog
description: PostgreSQL WAL/XLOG checklist for adding or modifying a WAL record — choosing builtin rmgr vs Generic WAL (generic_xlog.c) vs custom rmgr (RegisterCustomRmgr), XLogInsert + XLogRegisterBuffer idiom, writing a correct redo function, FPI/hint-bit (MarkBufferDirtyHint) rules, updating rmgrdesc and pg_waldump. Use when editing C that emits XLogInsert, adding an access method needing durability, or reviewing patches that change WAL record formats. Companion skills: `locking` for buffer-lock ordering around modified pages, `error-handling` for `ereport(PANIC, …)` inside redo. Do NOT trigger on MySQL binlog, SQLite WAL mode, Kafka logs, pgbackrest/wal_level config, or generic write-ahead-logging theory questions.
when_to_load: Emit a WAL record (`XLogInsert`); add or modify a custom rmgr; write a redo function; bump `XLOG_PAGE_MAGIC`; review WAL-record changes in a patch.
companion_skills:
  - locking
  - error-handling
  - replication-overview
  - access-method-apis
  - catalog-conventions
  - coding-style
---

# WAL & XLOG — operational skill

This is the procedural cookbook. For the conceptual model (LSNs, FPI,
checkpoints, rmgrs) read `knowledge/architecture/wal.md` first.

## When to use what

| Situation | Use |
|---|---|
| In-tree access method, new record type | new builtin rmgr (RmgrId < 128) — needs core patch |
| Extension that just modifies pages (small new index AM, prototype) | **Generic WAL** (`generic_xlog.c`) |
| Extension that needs compact records, logical decoding, or custom replay logic | **Custom rmgr** via `RegisterCustomRmgr` |
| Optimisation hint that can be re-derived from authoritative state | **no WAL** — use `MarkBufferDirtyHint()` |
| Tracking commit/abort of an XID (you almost never need to do this) | not a WAL concern — it's pg_xact |

[from-comment `source/src/backend/access/transam/rmgr.c:97-104`;
from-code `source/src/backend/access/transam/generic_xlog.c:1-12`]

## Custom rmgr vs Generic WAL — decision

Choose **Generic WAL** when:
- You're prototyping or your extension is small.
- Record volume isn't a bottleneck (per-page delta can be larger than a
  hand-rolled record).
- You don't need logical decoding.

Choose **Custom rmgr** when:
- Record volume matters (frequent small changes).
- You need replay-time semantics beyond "apply this page delta" (e.g.
  cross-page invariants, structure-specific recovery).
- You need a `rm_decode` hook for logical decoding.
- You want pretty `pg_waldump` output via `rm_desc` / `rm_identify`.

## Custom rmgr — full checklist

### 1. Reserve an RmgrId

- Valid custom range: `128 ≤ rmid ≤ 255` (`RM_MIN_CUSTOM_ID` ..
  `RM_MAX_CUSTOM_ID`). [verified-by-code
  `source/src/include/access/rmgr.h:35-36`]
- During development use `RM_EXPERIMENTAL_ID = 128`. [verified-by-code
  `rmgr.h:60`]
- For release: register your unique ID at
  <https://wiki.postgresql.org/wiki/CustomWALResourceManagers> so it
  doesn't collide with another extension. [from-comment `rmgr.c:99-104`]

### 2. Define the `RmgrData` struct

In your extension's headers/source, define a static `RmgrData` filling at
least:

```c
static const RmgrData my_rmgr = {
    .rm_name      = "my_extension",
    .rm_redo      = my_redo,
    .rm_desc      = my_desc,
    .rm_identify  = my_identify,
    .rm_startup   = NULL,         /* optional */
    .rm_cleanup   = NULL,         /* optional */
    .rm_mask      = my_mask,      /* needed for wal_consistency_checking */
    .rm_decode    = NULL,         /* optional; only if records should be
                                     visible to logical decoding plugins */
};
```

[verified-by-code `source/src/include/access/xlog_internal.h:351-362`]

### 3. Register from `_PG_init`

```c
void
_PG_init(void)
{
    if (!process_shared_preload_libraries_in_progress)
        ereport(ERROR,
                (errcode(ERRCODE_INVALID_PARAMETER_VALUE),
                 errmsg("my_extension must be loaded via shared_preload_libraries")));
    RegisterCustomRmgr(RM_EXPERIMENTAL_ID, &my_rmgr);
}
```

`RegisterCustomRmgr` will `ereport(ERROR)` if:
- the name is empty,
- the rmid is outside the custom range,
- you're not in `shared_preload_libraries`,
- the rmid is already taken,
- the name (case-insensitive) collides with another loaded rmgr.

[verified-by-code `source/src/backend/access/transam/rmgr.c:107-146`]

### 4. Emit records (writer side)

The five-step write rule from `transam/README:437-470` is mandatory:

```c
/* 1. Pin & exclusive-lock all buffers we'll modify */
LockBuffer(buf, BUFFER_LOCK_EXCLUSIVE);

START_CRIT_SECTION();           /* 2. errors from here on = PANIC */

/* 3. Apply changes to the page in shared buffers */
modify_page(buf);

MarkBufferDirty(buf);           /* 4. BEFORE the WAL insert */

/* 5. Build & insert the WAL record */
XLogBeginInsert();
XLogRegisterBuffer(0, buf, REGBUF_STANDARD);
XLogRegisterData(&xlrec, SizeOfMyXlog);          /* main data */
XLogRegisterBufData(0, payload, payload_len);    /* per-block data */
recptr = XLogInsert(MY_RMGR_ID, XLOG_MY_OP);
PageSetLSN(BufferGetPage(buf), recptr);

END_CRIT_SECTION();             /* 6 */

UnlockReleaseBuffer(buf);       /* 7 */
```

Pre-flight checks (page-full, etc.) must happen *before*
`START_CRIT_SECTION()`. [from-README `transam/README:441-446`]

`REGBUF_*` choice cheatsheet:
- `REGBUF_STANDARD` — standard page (hole stripped from FPI). Use this
  whenever you can.
- `REGBUF_WILL_INIT` — redo will recreate the page from scratch (use for
  page-initialising records like btree split's right page).
- `REGBUF_FORCE_IMAGE` — force FPI even if not first-after-checkpoint;
  useful when you rewrite most of the page anyway.
- `REGBUF_KEEP_DATA` — keep the registered block data in the record even
  when an FPI is taken.
- `REGBUF_NO_IMAGE` — never take an FPI. Rarely correct; only if torn-page
  risk is genuinely zero. [verified-by-code
  `source/src/include/access/xloginsert.h:31-41`]

Default working-area limits: 5 block refs, 20 data chunks. To exceed, call
`XLogEnsureRecordSpace(max_block_id, ndatas)` **before** `XLogBeginInsert()`
and **outside** the critical section. [from-README `transam/README:542-553`]

### 5. Write the redo function

Signature: `void my_redo(XLogReaderState *record)`. Use the decoding
helpers from `xlogreader.h` to extract data and buffer references.

```c
static void
my_redo(XLogReaderState *record)
{
    uint8       info = XLogRecGetInfo(record) & ~XLR_INFO_MASK;
    xl_my_op   *xlrec = (xl_my_op *) XLogRecGetData(record);
    Buffer      buf;
    XLogRedoAction action;

    switch (info)
    {
        case XLOG_MY_OP:
            action = XLogReadBufferForRedo(record, 0, &buf);
            if (action == BLK_NEEDS_REDO)
            {
                Page page = BufferGetPage(buf);
                /* apply the change exactly as the writer did */
                apply_change(page, xlrec);
                PageSetLSN(page, record->EndRecPtr);
                MarkBufferDirty(buf);
            }
            if (BufferIsValid(buf))
                UnlockReleaseBuffer(buf);
            break;
        default:
            elog(PANIC, "my_redo: unknown op code %u", info);
    }
}
```

`XLogReadBufferForRedo` return values you will hit
[verified-by-code `source/src/include/access/xlogutils.h:74-78`]:

| return | meaning | what to do |
|---|---|---|
| `BLK_NEEDS_REDO` | page LSN < record LSN; apply the change | apply, `PageSetLSN(page, record->EndRecPtr)`, `MarkBufferDirty` |
| `BLK_DONE` | page LSN ≥ record LSN; already applied | skip body, but still `UnlockReleaseBuffer` if `BufferIsValid` |
| `BLK_RESTORED` | FPI was just applied | skip body, page already at correct LSN |
| `BLK_NOTFOUND` | block doesn't exist (e.g. truncated) | nothing to do; buffer is invalid |

Use `record->EndRecPtr` (end of the record being replayed) for
`PageSetLSN` so the page LSN advances *past* the record once it's fully
applied — using the start LSN would leave the page LSN equal to the
record's start and falsely re-admit `BLK_NEEDS_REDO` on a re-scan that
restarts exactly at this record.

Hard rules for redo:
- **Idempotent**: must produce the right result regardless of how many
  times it's replayed, by virtue of the LSN check (`BLK_NEEDS_REDO` is
  only returned when the page's LSN is older than the record's).
- **No new WAL**: redo never emits WAL.
- **Lock order matters when multi-page**: if a record touches several
  buffers, acquire them in the same order the writer did, and don't
  release until all modifications are done — Hot Standby readers must
  not see intermediate states. [from-README `transam/README:614-619`]
- **Only the Startup process modifies pages during recovery**, so
  `PageSetLSN` without exclusive lock is fine there — but not from a
  hot-standby reader. [from-README `transam/README:620-626`]
- **No `MarkBufferDirtyHint`** in redo — there is no WAL to emit during
  recovery. [from-README `transam/README:638-642`]

### 6. Write `rm_desc` and `rm_identify`

Format conventions documented in
`source/src/backend/access/rmgrdesc/README:17-61`:

- JSON-style key/value, no top-level `{}`.
- Comma + space between fields. Spaces around colons.
- Length of an array appears *before* the array.
- Nested objects use `{}`. Use `rmgrdesc_utils.c` helpers for arrays.

Example:

```c
static void
my_desc(StringInfo buf, XLogReaderState *record)
{
    xl_my_op *xlrec = (xl_my_op *) XLogRecGetData(record);

    appendStringInfo(buf, "off: %u, flags: 0x%02X",
                     xlrec->offnum, xlrec->flags);
}

static const char *
my_identify(uint8 info)
{
    switch (info & ~XLR_INFO_MASK)
    {
        case XLOG_MY_OP: return "MY_OP";
        default:         return NULL;
    }
}
```

These show up in `pg_waldump` output and in `pg_get_wal_resource_managers()`.

### 7. Write `rm_mask` (for wal_consistency_checking)

`wal_consistency_checking` re-applies the record on a copy of the original
page and compares to the in-memory page. Some bits (hint bits, free-space
counters) legitimately differ between the two. `rm_mask` zeroes out those
bits on a page copy before comparison. Look at any existing
`*_mask` in `src/backend/access/*` for examples (e.g. `heap_mask`).

## Generic WAL — short form

```c
GenericXLogState *state = GenericXLogStart(rel);
Page  copy = GenericXLogRegisterBuffer(state, buf, GENERIC_XLOG_FULL_IMAGE);
modify_page(copy);          /* in the WAL workspace, not the real buffer */
XLogRecPtr lsn = GenericXLogFinish(state);
```

`GenericXLogFinish` computes the delta between the original and modified
page images, emits a `Generic` WAL record, and updates the real buffer.
Redo applies the delta. No custom redo function needed. [verified-by-code
`source/src/backend/access/transam/generic_xlog.c:1-44`]

Caveats:
- Up to `MAX_GENERIC_XLOG_PAGES` = `XLR_NORMAL_MAX_BLOCK_ID` = **4**
  pages per call. [verified-by-code
  `source/src/include/access/generic_xlog.h:23`,
  `source/src/include/access/xloginsert.h:28`]
- One transaction may emit many Generic records.
- Buffers are dirtied for you on `GenericXLogFinish`.

## Hint bits — when *not* to write WAL

Some changes are recoverable from authoritative state and can be skipped:
the canonical case is setting `HEAP_XMIN_COMMITTED` on a tuple after
checking pg_xact. Rules: [from-README `transam/README:629-665`]

- Use `MarkBufferDirtyHint()`, never `MarkBufferDirty()`.
- If the buffer is clean **and** (`data_checksums` or `wal_log_hints` is on),
  `MarkBufferDirtyHint()` itself emits `XLOG_FPI_FOR_HINT` to protect the
  page from torn writes.
- Recovery skips hint-only writes (no WAL is emitted during recovery anyway).

Replacing a `MarkBufferDirty()` call with `MarkBufferDirtyHint()` to "save
WAL" is only correct if the change is genuinely re-derivable. Otherwise
you've introduced silent corruption under torn-page conditions.

## Two-phase rmgr is special — skip unless you're rewriting twophase.c

`twophase.c` records PREPARE/COMMIT-PREPARED/ROLLBACK-PREPARED via its own
record types in the `Transaction` rmgr, and also stores per-prepared-xact
state files in `pg_twophase/` for crash recovery. You almost never want to
emit these directly. [from-comment
`source/src/backend/access/transam/twophase.c:12-19`]

## Pre-commit checklist for any WAL-touching patch

- [ ] All page modifications inside `START_CRIT_SECTION` / `END_CRIT_SECTION`.
- [ ] `MarkBufferDirty()` before `XLogInsert()`.
- [ ] `PageSetLSN()` after `XLogInsert()` on every modified buffer.
- [ ] Every modified buffer is `XLogRegisterBuffer`'d (else torn-page hazard).
- [ ] If using `REGBUF_NO_IMAGE`, an explicit comment justifies why.
- [ ] Multi-page records: writer and redo use the same buffer lock order.
- [ ] Redo function is idempotent and only modifies pages when
      `XLogReadBufferForRedo` returns `BLK_NEEDS_REDO`.
- [ ] **Writer ↔ redo symmetry**: for every field the writer reads from
      the in-memory state, the corresponding bytes are written into the
      record via `XLogRegisterData` / `XLogRegisterBufData` and read back
      via `XLogRecGetData` / `XLogRecGetBlockData` in redo. This bug
      class survives `wal_consistency_checking=all` (the writer never
      produces a diverging on-disk page) — only crash recovery exposes it.
- [ ] `rm_desc` and `rm_identify` implemented (and follow the
      `rmgrdesc/README` formatting).
- [ ] `rm_mask` implemented if the record can leave hint-bit-like
      differences.
- [ ] If running under `wal_level=minimal`, the access method either
      respects `RelationNeedsWAL()` or implements one of the two
      exception protocols (`FlushRelationBuffers + smgrimmedsync`, or
      unconditional WAL). [from-README `transam/README:746-775`]
- [ ] Tested under `wal_consistency_checking = 'all'` (or your rmgr name).
- [ ] Tested under `wal_compression` ∈ {off, pglz, lz4, zstd} if
      applicable.

## Useful greps for finding examples

- All redo entry points: `grep -RIn '_redo(' src/backend/access`
- All `rm_mask` implementations: `grep -RIn '_mask(' src/backend/access`
- `XLogInsert` callers (writer-side patterns):
  `grep -RIn 'XLogInsert(' src/backend/access | head`
- Existing custom-rmgr extensions (contrib): `ls contrib/` and look at
  `bloom/` — it uses Generic WAL, not a custom rmgr, but is a good
  minimal-extension example.

## Open questions to verify on first real use

- `rm_decode` is **optional**: `decode.c` checks `if (rmgr.rm_decode != NULL)`
  before invoking it. Set it only if you want your rmgr's records to be
  visible to logical decoding plugins. [verified-by-code
  `source/src/backend/replication/logical/decode.c:116-117`]
- `[unverified]` Behaviour of `XLogRegisterBlock` (the lower-level variant
  of `XLogRegisterBuffer`) — used by recovery-friendly paths that don't
  have a Buffer yet; signature in `xloginsert.h:51-53`.

## Cross-references

- `.claude/skills/locking/SKILL.md` — buffer-content lock ordering around modified pages; WAL-before-data rule.
- `.claude/skills/error-handling/SKILL.md` — `ereport(PANIC, …)` inside redo; redo functions can't `ereport(ERROR)`.
- `.claude/skills/replication-overview/SKILL.md` — walsender / walreceiver consumers of WAL records; logical decoding `rm_decode`.
- `.claude/skills/access-method-apis/SKILL.md` — AM-specific rmgrs for index / table AMs.
- `.claude/skills/catalog-conventions/SKILL.md` — `XLOG_PAGE_MAGIC` bump rules; `pg_control` version bumps.
- `.claude/skills/coding-style/SKILL.md` — backend C style for redo functions, rmgrdesc structures.
- `knowledge/architecture/wal.md` — long-form WAL design discussion.
- `source/src/backend/access/transam/README` — canonical XLOG-record format discussion.
