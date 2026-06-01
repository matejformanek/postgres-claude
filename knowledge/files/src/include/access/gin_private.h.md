# gin_private.h

- **Source path:** `source/src/include/access/gin_private.h` (540 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The implementation-internal API of GIN: shared by every file in `src/backend/access/gin/`. Defines `GinState` (per-relation opclass cache), `GinScanOpaque` + scan-key state, the `GinBtree` abstract vtable + stack frames, and all the entry-point prototypes. [from-comment, gin_private.h:1-9]

## Major types

- `GinOptions` — reloptions: `useFastUpdate`, `pendingListCleanupSize`.
- `GinState` — `compareFn`, `extractValueFn`, `extractQueryFn`, `consistentFn`, `comparePartialFn`, `triConsistentFn`, `oneCol`, `origTupdesc`, `tupdesc[INDEX_MAX_KEYS]` etc. Held in `IndexInfo->ii_AmCache`.
- `GinBtree` / `GinBtreeStack` — the abstract B-tree engine vtable used by `ginbtree.c`.
- `GinBtreeEntryInsertData` / `GinBtreeDataLeafInsertData` — payloads for `beginPlaceToPage`.
- `GinScanOpaqueData`, `GinScanKey`, `GinScanEntry` — scan-time state.
- `BuildAccumulator` — used by `ginbulk.c` for build-time key accumulation.
- `GinStatsData` — per-build counters (`nEntryPages`, `nDataPages`, etc.).

## Constants

- `GIN_DEFAULT_USE_FASTUPDATE = true`.
- `GIN_DEFAULT_PENDING_LIST_CLEANUP_SIZE = 4MB`.

## Prototypes

Hundreds of function prototypes spanning ginutil/ginbtree/ginentrypage/gindatapage/gininsert/ginscan/ginget/ginvacuum/ginfast/ginlogic/ginpostinglist.
