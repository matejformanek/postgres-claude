# `src/backend/utils/sort/tuplestore.c`

- **File:** `source/src/backend/utils/sort/tuplestore.c` (1680 lines)
- **Header:** `source/src/include/utils/tuplestore.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Materialized intermediate result. "A dumbed-down version of tuplesort.c;
it does no sorting of tuples but can only store and regurgitate a
sequence of tuples." (`tuplestore.c:6-9` [from-comment]) Used for
Materialize plan nodes, hashjoin batches, holdable cursors, SRF results,
WITH HOLD / WITH RECURSIVE intermediate state, and trigger transition
tables. Two distinguishing capabilities from tuplesort: **reading can
start before writing finishes** (`:10-13`) and **multiple independent
read pointers** are supported (`:13-14, 25-27`).

## Three-state machine

`TupStoreStatus` (`:73-78`):
- **`TSS_INMEM`** — `memtuples[]` pointer array holds everything;
  read pointers carry an `int current` index.
- **`TSS_WRITEFILE`** — appending to a `BufFile`; "the temp file's seek
  position is the current write position" (`:38-41` [from-comment]).
- **`TSS_READFILE`** — "the temp file's seek position is the active read
  pointer's position" (`:41-43` [from-comment]).

Switches between WRITEFILE and READFILE save/restore `ftell()` positions
because BufFile has only one underlying seek position; multiple read
pointers and the implicit "write position" all share it.

## Why it isn't just a tuplesort

Differences from `tuplesort.c`:
- **Read can begin before write completes** (`:10-13` [from-comment]) —
  there is no `performsort` boundary; you can interleave `puttuple` and
  `gettupleslot` on read pointer 0.
- **Multiple read pointers** via `tuplestore_alloc_read_pointer`
  (`:396`). Each `TSReadPointer` has `eflags`, `eof_reached`, and either
  a `current` array index (INMEM) or a `(file, offset)` pair (file
  states). `:92-99`.
- **`tuplestore_trim`** (`:1457-1547`): if no read pointer needs rewind
  and we're INMEM, slide the array down to the oldest active read
  position (minus one — see comment at `:1486-1494`, "we keep one extra
  tuple before the oldest current" because callers may still hold a
  pointer to the previously-returned tuple). Skips slide-down when
  `nremove < memtupcount/8` to avoid O(N²) memmove churn.
- **Mark/restore via copying read pointers** (`tuplestore_copy_read_pointer`,
  `:1330`) — no separate mark slot like tuplesort has.
- **Backward scan** is a constructor-time choice (`randomAccess`
  parameter to `tuplestore_begin_heap`), because it changes the on-disk
  format (it stores a trailing length word per tuple).

## State invariants

- `eflags` (`:107`) is the OR of all read pointers' eflags — once a
  capability has been requested at any read pointer, you can't drop it.
- `tuplestore_set_eflags` (`:372`) is "must be called before putting any
  tuples", since enabling backward scan changes the file format. [from-comment]
- `interXact` (`:109`) — when true, the tuplestore (and any temp file)
  survive transaction boundaries. Resource owner is the
  `TopTransactionResourceOwner` instead of CurrentResourceOwner.
- `truncated` (`:110`) — set only when `tuplestore_trim` actually
  removed tuples; used for Assert crosschecks (`:1517`).

## Public API surface

Lifecycle:
- `tuplestore_begin_heap(randomAccess, interXact, maxKBytes)` (`:331`).
- `tuplestore_set_eflags(state, eflags)` (`:372`) — set on read pointer 0.
- `tuplestore_alloc_read_pointer(state, eflags)` (`:396`) — returns int
  pointer ID; new pointer starts at current read-pointer-0 position.
- `tuplestore_select_read_pointer(state, ptr)` (`:508`) — switch active.
- `tuplestore_clear(state)` (`:431`) — keep state, drop tuples (resets
  position to start).
- `tuplestore_end(state)` (`:493`) — free everything.

Write:
- `tuplestore_puttupleslot(state, slot)` (`:743`) — minimal-tuple copy.
- `tuplestore_puttuple(state, HeapTuple)` (`:765`).
- `tuplestore_putvalues(state, tdesc, values, isnull)` (`:785`) — form
  MinimalTuple from raw Datums.

Read (against the active read pointer):
- `tuplestore_gettupleslot(forward, copy, slot)` (`:1131`).
- `tuplestore_gettupleslot_force` (`:1163`).
- `tuplestore_advance` (`:1195`), `tuplestore_skiptuples` (`:1220`).
- `tuplestore_rescan` (`:1329`) — set active back to start.
- `tuplestore_ateof` (`:592`).
- `tuplestore_in_memory` (`:1601`).
- `tuplestore_trim` (`:1457`), `tuplestore_get_stats` (`:1580`).

## Key data

- **`Tuplestorestate`** (`:104-…`) — `memtuples[]` is `void **` (array of
  pointers, not embedded SortTuples — no `datum1` cache because there's
  no sort key), plus `memtupcount`, `memtupdeleted` (count of slid-down
  slots that hold NULL), `memtupsize`, `readptrs[]`/`readptrcount`/
  `activeptr`, `BufFile *myfile`, `MemoryContext context`,
  `ResourceOwner resowner`.
- **Callback table**: `copytup`, `writetup`, `readtup` (`:120-…`) —
  same shape as tuplesort's TuplesortPublic but inlined into the struct.
  Currently only the heap variant exists; the indirection is kept "so
  that extension to other kinds of objects will be easy if it's ever
  needed" (`:125-128` [from-comment]).

## Cross-references

- Storage: `BufFile` (`source/src/backend/storage/file/buffile.c`) — the
  spill file. Tuplestore uses `BufFileSeek`/`Tell`/`Read`/`Write`.
- Executor consumers: `Materialize` plan node
  (`source/src/backend/executor/nodeMaterial.c`),
  `nodeFunctionscan.c` (SRFs that materialize), `WindowAgg`
  (`nodeWindowAgg.c`), CTEs (`nodeCtescan.c` — actually uses tuplestore
  via WorkTableScan / RecursiveUnion), holdable cursors
  (`portalmem.c`).
- `tuplesort.c` — the older, larger sibling whose callback pattern this
  file copied.

## Open questions

- Exact temp-tablespace lookup for `BufFileCreateTemp` here — only
  skimmed; tuplesort uses `PrepareTempTablespaces` and so does this
  [unverified].
- The relationship between `interXact = true` and the resource owner
  swap: comment says it uses `TopTransactionResourceOwner` but the
  precise lifecycle for cross-xact tuplestores is not chased.
- Behavior of `tuplestore_clear` mid-read on a temp-file backed
  tuplestore — does it discard the file or just rewind?

## Confidence tag tally

- `[verified-by-code]` × ~7
- `[from-comment]` × ~6
- `[unverified]` × 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/memory-context-slab-generation-bump.md](../../../../../idioms/memory-context-slab-generation-bump.md)

