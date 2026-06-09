# contrib/bloom/blinsert.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 343
**Verification depth:** full read

## Role

Bloom index build (`blbuild`) and per-tuple insert (`blinsert`) paths.
`blbuild` does a single table-scan via `table_index_build_scan`, filling
an in-memory cached page and flushing it under `generic_xlog`. `blinsert`
appends a single tuple, preferring pages listed in the metapage's
`notFullPage[]` cursor before extending the relation.
[verified-by-code] `source/contrib/bloom/blinsert.c:1-29`

## Public API

- `PG_MODULE_MAGIC_EXT(.name="bloom", .version=PG_VERSION)` — the module
  magic lives in this file (alongside `blbuild`).
  [verified-by-code] `source/contrib/bloom/blinsert.c:25-28`
- `blbuild(heap, index, indexInfo) → IndexBuildResult*`
  [verified-by-code] `source/contrib/bloom/blinsert.c:121-159`
- `blbuildempty(index)` — initializes the meta page in `INIT_FORKNUM`
  (unlogged-relation reset path).
  [verified-by-code] `source/contrib/bloom/blinsert.c:164-169`
- `blinsert(index, values, isnull, ht_ctid, heapRel, checkUnique,
  indexUnchanged, indexInfo) → bool` — returns false unconditionally
  (no uniqueness, no extra signaling).
  [verified-by-code] `source/contrib/bloom/blinsert.c:174-342`

## Invariants

- INV-1: All page modifications go through `generic_xlog` — every
  successful path calls `GenericXLogFinish`, every aborted path calls
  `GenericXLogAbort`. The state machine is hand-rolled (one of the
  more intricate `generic_xlog` uses in the tree).
  [verified-by-code] `source/contrib/bloom/blinsert.c:51-58, 222-242, 272-310, 318-336`
- INV-2: `blbuild` errors out if the index already has any blocks
  ("index already contains data"). Prevents accidental re-build over
  existing data.
  [verified-by-code] `source/contrib/bloom/blinsert.c:128-130`
- INV-3: Build uses a private per-tuple `tmpCtx` reset after every
  tuple — bounded memory regardless of relation size.
  [verified-by-code] `source/contrib/bloom/blinsert.c:138-141, 78-115`
- INV-4: `blinsert` always returns `false` — bloom doesn't support
  uniqueness checks.
  [verified-by-code] `source/contrib/bloom/blinsert.c:240, 303, 341`
- INV-5: Recycled "deleted" pages discovered via the `notFullPage` list
  are detected (`PageIsNew || BloomPageIsDeleted`) and re-initialized
  before reuse.
  [verified-by-code] `source/contrib/bloom/blinsert.c:228-230, 290-292`
- INV-6: Meta-page lock discipline: shared read first to peek at
  `nStart`, then exclusive only after we know we need to write metadata.
  [verified-by-code] `source/contrib/bloom/blinsert.c:207-217, 257`

## Notable internals

- **Two-pass insert strategy**:
  1. Try the first page in `notFullPage` cursor under shared metaLock.
     If it accepts, drop ALL locks and return.
  2. Otherwise upgrade metaLock to exclusive and iterate through the
     remaining `notFullPage` entries.
  3. If none accept, extend the relation via `BloomNewBuffer`, RESET
     `notFullPage = [new]`, and write it.
  [verified-by-code] `source/contrib/bloom/blinsert.c:203-336`
- **Author-flagged concern** at line 313: "XXX is it good to do this
  while holding ex-lock on the metapage??" — the relation extension
  happens with the metapage exclusively locked. This serializes
  inserters when extending. Known wart, not a bug.
  [from-comment] `source/contrib/bloom/blinsert.c:312-315`
- **`flushCachedPage`** uses `GENERIC_XLOG_FULL_IMAGE` because the page
  was constructed from scratch in memory — easier (and required) to
  WAL it as a full image.
  [verified-by-code] `source/contrib/bloom/blinsert.c:47-58`

## Trust-boundary / Phase-D surface

- **All buffer modifications WAL-logged via generic_xlog** — no replica
  divergence risk specific to bloom; correctness inherited from
  generic_xlog's redo path.
- **Re-initialization of recycled pages** [verified-by-code:228-230,
  290-292] is critical: skipping it could read stale tuple bytes into
  a new context. The check `PageIsNew || BloomPageIsDeleted` is both
  necessary and sufficient (vacuum sets `BloomPageSetDeleted`; raw new
  pages get `PageIsNew`).
- **`notFullPage` is advisory only** — if vacuum updates it concurrently,
  the second-pass loop re-reads `nStart`/`nEnd` under exclusive lock
  (line 260) so a race window between the shared and exclusive lock is
  benign (worst case: re-try the same page once).
- **Memory contexts** — per-insert `insertCtx` is created and destroyed
  for every `blinsert` call. Allocation/free pattern looks safe; no
  leak observed.
  [verified-by-code] `source/contrib/bloom/blinsert.c:194-340`

## Cross-refs

- `source/src/backend/access/transam/generic_xlog.c` — WAL backend.
- `source/src/backend/access/table/tableam.c` —
  `table_index_build_scan`.
- `source/src/backend/storage/buffer/bufmgr.c` — `ExtendBufferedRel`.

## Issues raised

- **ISSUE-D1 (low)** — relation extension under exclusive meta-page lock
  serializes inserters during extends. Author-acknowledged
  (XXX comment line 313).
