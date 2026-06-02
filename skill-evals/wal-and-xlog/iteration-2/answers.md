# Iteration 2 — Answers

Same three prompts as iter-1. Re-answered honestly against the *updated*
SKILL.md (with iter-1's seven edits applied) and a fresh baseline.

---

## E1 — Generic WAL vs custom rmgr

### with_skill

For a small contrib index AM whose only durability requirement is crash safety, use **Generic WAL** (`access/generic_xlog.c`):

```c
GenericXLogState *state = GenericXLogStart(rel);
Page copy = GenericXLogRegisterBuffer(state, buf, GENERIC_XLOG_FULL_IMAGE);
modify_page(copy);          /* edit the workspace copy, not the live buffer */
XLogRecPtr lsn = GenericXLogFinish(state);
```

`GenericXLogFinish` diffs the original page image vs the modified copy, emits one `Generic`-rmgr record carrying the delta, marks the real buffer dirty, and returns the LSN. Replay applies the delta on its own — you write no redo function, no `rm_desc`, no `rm_identify`. Cap is `MAX_GENERIC_XLOG_PAGES = XLR_NORMAL_MAX_BLOCK_ID = 4` pages per call (`source/src/include/access/generic_xlog.h:23`, `xloginsert.h:28`). One transaction may emit many records.

Choose a **custom rmgr** instead when any of:

1. **Record volume matters.** A hand-rolled compact record beats the per-page delta when changes are small and frequent.
2. **Replay-time semantics richer than "apply delta".** Cross-page invariants, structure-aware recovery (btree split is the canonical example).
3. **Logical decoding** — set the optional `rm_decode` hook (`decode.c:116-117` only calls it if non-NULL).
4. **Pretty `pg_waldump` output** via `rm_desc` / `rm_identify`.

Custom rmgr requires an `RmgrId` in `128..255` (`RM_MIN_CUSTOM_ID..RM_MAX_CUSTOM_ID`, `rmgr.h:35-36`), registered via `RegisterCustomRmgr` from `_PG_init` (must be loaded in `shared_preload_libraries` — else `ereport(ERROR)`). `RM_EXPERIMENTAL_ID = 128` is for development. For release, reserve your ID at <https://wiki.postgresql.org/wiki/CustomWALResourceManagers> to avoid collisions with other extensions.

`contrib/bloom/` is the canonical minimal Generic-WAL extension to copy from.

### baseline

For a small contrib index the usual answer is Generic WAL — there's a helper in `generic_xlog.c` that handles redo for you so you don't have to write a resource manager. Trade-offs vs writing a full custom rmgr: with Generic WAL you can't get logical decoding visibility, your `pg_waldump` output will all be lumped under "Generic" so debugging is harder, and the per-page delta encoding is fatter than a hand-rolled record so for write-heavy AMs the WAL volume can be noticeable. Custom rmgr means you write `rm_redo`, `rm_desc`, `rm_identify`, optionally `rm_mask` for `wal_consistency_checking`, and register via `RegisterCustomRmgr` from `_PG_init`. I don't recall the exact ID range — somewhere in the upper half of the byte, reserved for extensions.

---

## E2 — Writer-side idiom

### with_skill

The mandatory seven-step schema from `transam/README:437-470`:

```c
LockBuffer(buf, BUFFER_LOCK_EXCLUSIVE);     /* 1. pin+xlock every target buffer */

/* Pre-flight checks (page-full? need split?) — BEFORE crit-section */

START_CRIT_SECTION();                       /* 2. errors here onward = PANIC */

modify_page(buf);                           /* 3. apply page changes */

MarkBufferDirty(buf);                       /* 4. MUST precede the WAL insert */

XLogBeginInsert();                          /* 5. assemble the record */
XLogRegisterBuffer(0, buf, REGBUF_STANDARD);
XLogRegisterData(&xlrec, SizeOfMyXlog);
XLogRegisterBufData(0, payload, payload_len);
recptr = XLogInsert(MY_RMGR_ID, XLOG_MY_OP);
PageSetLSN(BufferGetPage(buf), recptr);     /* on EVERY modified buffer */

END_CRIT_SECTION();                         /* 6 */
UnlockReleaseBuffer(buf);                   /* 7 */
```

Hard placement rules:

- `MarkBufferDirty` **before** `XLogInsert`. The bufmgr flush path interlocks against this ordering; reversing it lets a concurrent flush race the WAL emission.
- `PageSetLSN` **after** `XLogInsert`, on **every** modified buffer.
- Pre-flight checks belong **outside** the critical section — once inside, every `ereport` is promoted to PANIC.
- Need more than the defaults (5 block refs, 20 data chunks)? Call `XLogEnsureRecordSpace(max_block_id, ndatas)` **before** `XLogBeginInsert` and **outside** the critical section (`transam/README:542-553`).

`REGBUF_*` cheatsheet (`source/src/include/access/xloginsert.h:31-41`):

- `REGBUF_STANDARD` — strip the hole between `pd_lower..pd_upper` from any FPI; the right default.
- `REGBUF_WILL_INIT` — redo recreates the page from scratch (btree-split's right page).
- `REGBUF_FORCE_IMAGE` — force FPI; useful when most of the page is rewritten anyway.
- `REGBUF_KEEP_DATA` — keep registered block data even when an FPI is taken.
- `REGBUF_NO_IMAGE` — never take an FPI; rarely correct. Demand a justifying comment.

Multi-page changes must be split into a chain of self-consistent atomic records — replay can be interrupted at any point. Btree-split is the worked example: it sets an `incomplete_split` flag on the parent and finishes the link in a later record.

### baseline

Lock the buffer exclusive, start critical section, modify the page in memory, MarkBufferDirty, then build the WAL record with XLogBeginInsert + XLogRegisterBuffer + XLogRegisterData + XLogInsert, PageSetLSN it on each modified buffer, end critical section, unlock. The crit-section turns any ereport into PANIC which is what you want for half-applied page changes. REGBUF_STANDARD is the usual flag. I think MarkBufferDirty must come before XLogInsert but I sometimes get the order wrong.

---

## E3 — Redo function rules

### with_skill

Signature: `void my_redo(XLogReaderState *record)`. Skeleton:

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
                apply_change(page, xlrec);          /* same change as writer */
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

`XLogReadBufferForRedo` returns one of four values (`xlogutils.h:74-78`):

| return | meaning | action |
|---|---|---|
| `BLK_NEEDS_REDO` | page LSN < record LSN | apply; `PageSetLSN(page, record->EndRecPtr)`; `MarkBufferDirty` |
| `BLK_DONE` | already at or past record LSN | skip body; still `UnlockReleaseBuffer` if valid |
| `BLK_RESTORED` | FPI just applied | skip body; page already correct |
| `BLK_NOTFOUND` | block doesn't exist | nothing to do |

Use `record->EndRecPtr` (not the start LSN) so the page LSN advances *past* the record once fully applied — using the start LSN would leave the page LSN equal to the record's start and falsely re-admit `BLK_NEEDS_REDO` on a re-scan that restarts exactly at this record.

Hard rules:

- **Idempotent via LSN check.** `BLK_NEEDS_REDO` is only returned when the page LSN is older than the record's.
- **No new WAL during redo.** Recovery never emits WAL.
- **No `MarkBufferDirtyHint` during redo** — it would try to emit `XLOG_FPI_FOR_HINT` and there's no WAL pipe.
- **Multi-buffer lock order matches the writer.** Hot Standby readers must not see intermediate states; acquire buffers in the same order and hold all locks until every modification is done.
- **Only the Startup process modifies pages during recovery**, but Hot Standby readers can hold shared content locks concurrently, so the buffer must still be exclusive while you mutate it.
- **Writer ↔ redo symmetry**: every field the writer reads from in-memory state must be serialised via `XLogRegisterData`/`XLogRegisterBufData` and read back here via `XLogRecGetData`/`XLogRecGetBlockData`. This is the bug class `wal_consistency_checking` *cannot* catch — only a crash exposes it.

Test under `wal_consistency_checking = 'all'` (or your rmgr name) — that requires an `rm_mask` to zero out hint-bit-like differences.

### baseline

The redo function takes an `XLogReaderState`. Switch on the info byte masked with `~XLR_INFO_MASK`. For each registered buffer call `XLogReadBufferForRedo` — it tells you whether the page needs redo, was restored from FPI, or is already past this record. If `BLK_NEEDS_REDO`, apply the change, `PageSetLSN`, `MarkBufferDirty`, unlock. No new WAL in redo. Multi-buffer records need matching lock order with the writer for Hot Standby safety. I usually have to look up whether `PageSetLSN` takes the start or end LSN of the record.
