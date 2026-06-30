# ginutil.c

- **Source path:** `source/src/backend/access/gin/ginutil.c` (681 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The `ginhandler` AM vtable, page-init helpers (`GinInitBuffer`, `GinInitMetabuffer`), allocation helpers (`GinNewBuffer`), opclass-cache (`GinState`), and the high-level `ginEntryInsert` wrapper that decides "inline posting list vs. promote-to-posting-tree". [from-comment, ginutil.c:1-13]

## `ginhandler`

Registers GIN's `IndexAmRoutine`: bitmap-only (`amgetbitmap=gingetbitmap`, `amgettuple=NULL`), supports backward scan = false, supports parallel scan = false but parallel build = true (via `_gin_parallel_*` in `gininsert.c`), `amclusterable=false`, `amcanmulticol=true`, `amsearchnulls=true`. [verified-by-code, ginutil.c:`ginhandler`]

## `GinState`

The per-relation opclass-procedure cache: looks up `compare` (1), `extractValue` (2), `extractQuery` (3), `consistent` (4 boolean) / `triConsistent` (6 ternary), `comparePartial` (5), `options` (7). Held in `IndexInfo->ii_AmCache`. [verified-by-code, struct in `gin_private.h`]

## Page-init helpers

- `GinInitPage(page, flags, size)` — generic init: `PageInit` + set GIN opaque flags.
- `GinInitBuffer(buf, flags)` — init a freshly-allocated buffer.
- `GinInitMetabuffer(buf)` — init the metapage with `GIN_META_PAGE_FLAG`.
- `GinNewBuffer` — try FSM, else extend relation; **uses indexfsm.c, not pg_freespacemap.c** (FSM lives in the index's FSM fork).

## `ginEntryInsert` orchestration

The high-level entry-tree insert called by `gininsert.c`:
1. Search entry tree for the key.
2. If found and target leaf entry has an inline posting list with room: append the new TID(s) via `addItemPointersToLeafTuple` (handled inside `entryExecPlaceToPage`).
3. If inline would overflow: create posting tree via `createPostingTree` (in `gindatapage.c`), replace leaf tuple with posting-tree-pointer form.
4. If not found: insert a new leaf tuple containing the TID(s) inline.

## Cross-references

Many sites; this is the file other GIN code includes via `gin_private.h`.

Tags: [from-comment, ginutil.c:1-15]; AM vtable [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/gin-tree-structure.md](../../../../../idioms/gin-tree-structure.md)

