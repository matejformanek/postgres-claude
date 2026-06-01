# gininsert.c

- **Source path:** `source/src/backend/access/gin/gininsert.c` (2478 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `ginbtree.c` (entry-tree engine), `ginentrypage.c` (entry-tree leaf format), `ginfast.c` (fastupdate path), `ginbulk.c` (build accumulator).

## Purpose

Top-level insert wrapper (`gininsert`) + the AM's parallel build coordinator. Sits above `ginEntryInsert` (in `ginutil.c`/`ginentrypage.c`) and below the AM-callable surface (`ginhandler` in `ginutil.c`). Hosts `ginbuild`/`ginbuildempty`. [from-comment, gininsert.c:1-12]

## Key entry points

| Function | Role |
|---|---|
| `gininsert` (AM slot) | Per-row insert. If `fastupdate=on`, hand off to `ginHeapTupleFastInsert` (in `ginfast.c`). Else extract keys via opclass `extractValue`, call `ginEntryInsert` per key |
| `ginbuild` | The build path: feed tuplesort if parallel, else accumulate per-key in `BuildAccumulator` (in `ginbulk.c`) and flush at maintenance_work_mem |
| `ginbuildempty` | Init the metapage in the init fork via smgr bulk write |
| `ginInsertItemPointers` | Insert a sorted batch of TIDs into a posting tree (used by both build and fastupdate cleanup) |
| `_gin_parallel_*` | DSM-coordinated parallel build: `_gin_begin_parallel`, `_gin_end_parallel`, `_gin_parallel_main`, `_gin_parallel_scan_and_build` |

## Parallel build

Heavy: uses `Tuplesort` over `(key, category, heap_tid)` tuples (the `gin_tuple.h` format). Workers each scan a heap range and emit sorted entry tuples into a parallel tuplesort; the leader merges and inserts groups with identical key into the entry tree, building posting lists/trees in bulk.

## Locking notes

- Per-row insert takes no relation-level lock beyond the standard index insertion contract (caller holds row lock on heap tuple).
- Fastupdate: hands off to `ginfast.c`'s metapage-locking protocol (see `ginfast.c.md`).
- Build does no incremental WAL emission for the regular pages (`btree->isBuild` checks throughout `ginbtree.c` suppress WAL); the final `log_newpage` calls are issued by the bulk writer at end of build.

## Cross-references

- **Calls into:** `ginutil.c::ginEntryInsert`, `ginbtree.c::ginInsertValue`, `gindatapage.c::createPostingTree`, `ginfast.c::ginHeapTupleFastInsert`, `ginbulk.c::ginInsertBAEntry`.
- **Called by:** `IndexAmRoutine` slots via `index_insert` and `index_build`.

Tags: [from-comment, gininsert.c:1-12]; structure derived from function signatures + AM slots in `ginutil.c::ginhandler`.
