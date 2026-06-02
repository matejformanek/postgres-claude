# Iteration 1 — Answers

Each eval is answered twice: once **with_skill** (using SKILL.md + companion knowledge docs) and once **baseline** (what I'd say from general PG familiarity, no skill consultation).

---

## E1 — Generic WAL vs custom rmgr

### with_skill

For a small contrib index AM with crash safety as the only durability requirement, use **Generic WAL** (`access/generic_xlog.c`). Idiom:

```c
GenericXLogState *state = GenericXLogStart(rel);
Page copy = GenericXLogRegisterBuffer(state, buf, GENERIC_XLOG_FULL_IMAGE);
modify_page(copy);          /* edit the workspace copy, not the buffer */
XLogRecPtr lsn = GenericXLogFinish(state);
```

`GenericXLogFinish` diffs original vs modified page, emits a `Generic` rmgr record, dirties the real buffer, and returns the LSN. Redo applies the delta — you write no redo function. Up to `MAX_GENERIC_XLOG_PAGES` (small constant in `generic_xlog.h`) pages per call; one transaction may emit many records. Cite: `source/src/backend/access/transam/generic_xlog.c:1-44`.

Choose **custom rmgr** instead when any of: (a) record volume matters and the per-page delta is too fat vs a compact hand-rolled record; (b) you need replay-time semantics richer than "apply this page delta" (cross-page invariants, structure-aware recovery — btree split is the canonical example); (c) you want logical decoding via `rm_decode`; (d) you want pretty `pg_waldump` output via `rm_desc`/`rm_identify`. Custom rmgr requires an RmgrId in 128..255 registered via `RegisterCustomRmgr` from `_PG_init` (must be in `shared_preload_libraries`), and you must reserve it on <https://wiki.postgresql.org/wiki/CustomWALResourceManagers> to avoid collisions. `RM_EXPERIMENTAL_ID = 128` is for development.

`contrib/bloom/` is a good minimal Generic-WAL example.

### baseline

You'd typically use Generic WAL for an extension index — there's `generic_xlog.c` you can call into, and it handles redo for you. Alternative is to write your own resource manager but that's heavier — you need a redo function, desc functions, etc. For a small extension Generic WAL is the recommended path. I don't remember the exact custom rmgr ID range off the top of my head but I think extensions get a reserved range.

---

## E2 — Writer-side idiom

### with_skill

The mandatory schema (from `transam/README:437-470`) is seven steps:

```c
/* 1. Pin & exclusive-lock every buffer we'll modify */
LockBuffer(buf, BUFFER_LOCK_EXCLUSIVE);

/* Pre-flight checks (page-full? need to split?) BEFORE crit-section */

START_CRIT_SECTION();           /* 2. any error from here on PANICs */

modify_page(buf);               /* 3. apply in-memory page changes */

MarkBufferDirty(buf);           /* 4. MUST precede the WAL insert */

/* 5. Build & insert the WAL record */
XLogBeginInsert();
XLogRegisterBuffer(0, buf, REGBUF_STANDARD);
XLogRegisterData(&xlrec, SizeOfMyXlog);            /* main data */
XLogRegisterBufData(0, payload, payload_len);      /* per-block data */
recptr = XLogInsert(MY_RMGR_ID, XLOG_MY_OP);
PageSetLSN(BufferGetPage(buf), recptr);            /* on EVERY modified buffer */

END_CRIT_SECTION();             /* 6 */

UnlockReleaseBuffer(buf);       /* 7 */
```

Key rules:

- `MarkBufferDirty` must be **before** `XLogInsert` (see `SyncOneBuffer` for why — without it a flush could race the WAL emission).
- `PageSetLSN` must be **after** `XLogInsert` and called on every modified buffer.
- Pre-flight checks (will the row fit? does the page need a split?) belong **outside** the critical section; inside `START_CRIT_SECTION` every error escalates to PANIC.
- Need more than 5 block refs or 20 data chunks? Call `XLogEnsureRecordSpace(max_block_id, ndatas)` **before** `XLogBeginInsert` and **outside** the critical section.
- `REGBUF_*` flags pick FPI behavior: `REGBUF_STANDARD` (strip the pd_lower..pd_upper hole), `REGBUF_WILL_INIT` (redo recreates page — used by btree split's right page), `REGBUF_FORCE_IMAGE` (force FPI), `REGBUF_KEEP_DATA` (keep block data even when FPI taken), `REGBUF_NO_IMAGE` (rare; only if torn-page risk is truly zero — needs a justifying comment).
- Complex multi-page actions must be split into a chain of self-consistent WAL records, each individually atomic, because replay can be interrupted at any point. Btree split is the canonical worked example with the `incomplete_split` flag on the parent.

Cite: `source/src/backend/access/transam/README:437-486`, `source/src/include/access/xloginsert.h:31-65`.

### baseline

The general flow is: lock the buffer exclusive, start a critical section, modify the page, then do XLogBeginInsert, XLogRegisterBuffer for each modified buffer, XLogRegisterData for your record body, then XLogInsert returns an LSN, and you PageSetLSN it. End critical section, unlock. I think you need to MarkBufferDirty somewhere in there — probably before or right around the XLogInsert. REGBUF_STANDARD is the usual flag. Errors inside the critical section turn into PANICs which is the whole point — you can't have half-WAL-logged changes leaking out.

---

## E3 — Redo function rules

### with_skill

Signature: `void my_redo(XLogReaderState *record)`. Standard skeleton:

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
                apply_change(page, xlrec);     /* same change as writer */
                PageSetLSN(page, record->EndRecPtr);
                MarkBufferDirty(buf);
            }
            if (BufferIsValid(buf))
                UnlockReleaseBuffer(buf);
            break;
        default:
            elog(PANIC, "my_redo: unknown op %u", info);
    }
}
```

Hard rules:

- **Idempotent via LSN check.** `XLogReadBufferForRedo` returns `BLK_NEEDS_REDO` only when the page LSN is older than the record's — that's what makes replay safe to repeat. If you get `BLK_DONE` or `BLK_RESTORED` (FPI already applied), skip the body but still unlock.
- **No new WAL during redo.** Recovery never emits WAL.
- **No `MarkBufferDirtyHint` during redo** — it would try to emit `XLOG_FPI_FOR_HINT` and there's no WAL pipe.
- **Multi-buffer lock order matches the writer.** Hot Standby readers must never see intermediate states, so acquire buffers in the same order the writer did and hold all locks until all modifications are complete.
- **Only the Startup process modifies pages during recovery**, so `PageSetLSN` without an exclusive lock would technically be fine *from Startup* — but Hot Standby readers can be looking at the page concurrently with shared content locks, so the buffer must be held exclusive while you mutate it.
- **Use `record->EndRecPtr` for `PageSetLSN`** (not the start LSN — the end is what proves the record is fully applied).

Don't forget: implement `rm_mask` to zero out hint-bit-like differences for `wal_consistency_checking`, and test with `wal_consistency_checking = 'all'` (or your rmgr name).

Cite: `source/src/backend/access/transam/README:614-642`.

### baseline

The redo function takes an XLogReaderState. You typically loop on the info byte (masked with ~XLR_INFO_MASK), call something like XLogReadBufferForRedo to fetch the buffer — that returns an action telling you if you need to redo, if it was restored from an FPI, or if it's already at a newer LSN and you should skip. If BLK_NEEDS_REDO you apply the change and PageSetLSN and MarkBufferDirty. Don't emit any new WAL from redo. Multi-buffer records need careful lock ordering. I don't remember the exact LSN to set — start or end of the record.
