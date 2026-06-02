# Iteration 2 — Edits Applied to `.claude/skills/wal-and-xlog/SKILL.md`

All seven proposals from `iteration-1/proposed-edits.md` were applied. Values
verified against `source/...` before writing.

## Verifications

- `MAX_GENERIC_XLOG_PAGES` resolved to `XLR_NORMAL_MAX_BLOCK_ID` = **4**.
  - `source/src/include/access/generic_xlog.h:23` →
    `#define MAX_GENERIC_XLOG_PAGES XLR_NORMAL_MAX_BLOCK_ID`
  - `source/src/include/access/xloginsert.h:28` →
    `#define XLR_NORMAL_MAX_BLOCK_ID 4`
  - (iter-1 guess was correct; now inlined with both cites.)
- `rm_decode` mandatoryness: **optional**, called only when non-NULL.
  - `source/src/backend/replication/logical/decode.c:116-117` →
    `if (rmgr.rm_decode != NULL) rmgr.rm_decode(ctx, &buf);`
- `XLogReadBufferForRedo` return values enumerated against the actual enum
  at `source/src/include/access/xlogutils.h:74-78`
  (`BLK_NEEDS_REDO`, `BLK_DONE`, `BLK_RESTORED`, `BLK_NOTFOUND`).

## Edit log (proposal → change)

- **P1** Inlined `MAX_GENERIC_XLOG_PAGES = XLR_NORMAL_MAX_BLOCK_ID = 4` in the
  Generic WAL caveat; removed the `[unverified value — check at use site]`
  marker; cited `generic_xlog.h:23` + `xloginsert.h:28`.
- **P2** Added a paragraph below the redo example explaining why
  `record->EndRecPtr` (not the start LSN) is the correct argument to
  `PageSetLSN` in redo.
- **P3** Added the four-row `XLogReadBufferForRedo` return-value table
  (`BLK_NEEDS_REDO` / `BLK_DONE` / `BLK_RESTORED` / `BLK_NOTFOUND`) with the
  matching action column, cited to `xlogutils.h:74-78`.
- **P4** Added a "Writer ↔ redo symmetry" item to the pre-commit checklist:
  every field the writer reads from in-memory state must be serialised via
  `XLogRegisterData`/`XLogRegisterBufData` and read back via
  `XLogRecGetData`/`XLogRecGetBlockData` in redo.
- **P5** Retired the `[unverified]` on `rm_decode`; the open-questions block
  now states it as a verified optional hook with a code cite. Also updated
  the `RmgrData` struct example comment to match.
- **P6** Description frontmatter now mentions companion skills `locking` and
  `error-handling`.
- **P7** `_PG_init` snippet now uses a real `ereport(ERROR, (errcode(...),
  errmsg("my_extension must be loaded via shared_preload_libraries")))`
  instead of `ereport(ERROR, ...)` with literal ellipsis.

Two `[unverified]` markers remain in the open-questions block:

- `XLogRegisterBlock` behaviour (out of scope for this iteration — needs a
  read of `xloginsert.c`, not a one-line grep).
