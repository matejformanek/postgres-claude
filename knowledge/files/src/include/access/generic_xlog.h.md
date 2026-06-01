# generic_xlog.h

- **Source path:** `source/src/include/access/generic_xlog.h`
- **Lines:** 45
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `generic_xlog.c`, `xloginsert.h`.

## Purpose

The four-function public API for generic xlog records (open / register
buffer / finish / abort) plus the four rmgr-side callbacks
(`generic_redo`, `generic_identify`, `generic_desc`, `generic_mask`).
[from-comment] `generic_xlog.h:3-4`.

## Top-of-file comment (verbatim)

```
generic_xlog.h
   Generic xlog API definition.
```
[verified-by-code] `generic_xlog.h:3-4`.

## Key constants

- `MAX_GENERIC_XLOG_PAGES = XLR_NORMAL_MAX_BLOCK_ID` (=4) — max
  buffers per record. [verified-by-code] `generic_xlog.h:23`.
- `GENERIC_XLOG_FULL_IMAGE = 0x0001` — `flags` to
  `GenericXLogRegisterBuffer`; force a FPI. [verified-by-code]
  `generic_xlog.h:26`.

## Public surface

- `GenericXLogStart(Relation)` returns `GenericXLogState *`.
  [verified-by-code] `generic_xlog.h:33`.
- `GenericXLogRegisterBuffer(state, buffer, flags)` returns `Page` (a
  pointer into the working copy the caller mutates).
  [verified-by-code] `generic_xlog.h:34-35`.
- `GenericXLogFinish(state)` — `XLogRecPtr`. [verified-by-code]
  `generic_xlog.h:36`.
- `GenericXLogAbort(state)` — `generic_xlog.h:37` [verified-by-code]
- Rmgr callbacks: `generic_redo`, `generic_identify`, `generic_desc`,
  `generic_mask`. [verified-by-code] `generic_xlog.h:40-43`.

## Cross-references

- `generic_xlog.c` is the implementation; see for the fragment
  format.
- `contrib/bloom` is the canonical core user.

## Confidence tag tally

- `[verified-by-code]`: 9
- `[from-comment]`: 1
