# brin.c

- **Source path:** `source/src/backend/access/brin/brin.c` (3034 lines)
- **Last verified commit:** HEAD
- **Companion files:** `brin_pageops.c` (page-level update/insert), `brin_revmap.c` (heap-block→summary-tuple translation), `brin_tuple.c` (on-disk encoding), `brin_xlog.c` (WAL replay), `brin_minmax*.c`, `brin_bloom.c`, `brin_inclusion.c` (built-in opclasses).

## Purpose

The **public-interface module** of the BRIN access method. Defines `brinhandler` (the `IndexAmRoutine` vtable), the user-facing entry points (`brininsert`, `bringetbitmap`, `brinbuild`, `brinbulkdelete`, `brinvacuumcleanup`), the SQL-callable summarize/desummarize functions, and the parallel-build coordinator (`BrinShared`, `_brin_begin/end_parallel`, `_brin_parallel_*`). All page-level mechanics live in sibling files. [from-comment, brin.c:1-15]

## Capability vtable

`brinhandler` (line 254) declares the AM as: not ordered, not backward-scannable, no `amgettuple` (bitmap-only), multi-column capable, search-nulls, storage type pluggable, **not** parallel-scannable, but parallel-build-capable, summarizing (`amsummarizing=true`). [verified-by-code, brin.c:254-313]

| Slot | Function | Comment |
|---|---|---|
| `ambuild` | `brinbuild` | line 1110; sequential or parallel heap scan into in-memory summaries |
| `aminsert` | `brininsert` | line 349; "expand summary if heap value falls outside it" |
| `aminsertcleanup` | `brininsertcleanup` | line 517; frees the per-statement BrinInsertState |
| `ambulkdelete` | `brinbulkdelete` | line 1308; **no-op for tuple removal** — see §locking |
| `amvacuumcleanup` | `brinvacuumcleanup` | line 1323 — scans index pages reclaiming free space |
| `ambeginscan` / `amrescan` / `amendscan` | `brinbeginscan`, `brinrescan`, `brinendscan` | 544 / 964 / 983 |
| `amgetbitmap` | `bringetbitmap` | line 572; the entire read path |
| `amgettuple` | `NULL` | bitmap-only AM |
| `amvalidate` | `brinvalidate` | in `brin_validate.c` |
| `amoptions` | `brinoptions` | line 1353 |
| `amcostestimate` | `brincostestimate` | in `utils/adt/selfuncs.c` |

## Insert path (`brininsert`)

1. Read or create a per-statement `BrinInsertState` cached in `IndexInfo->ii_AmCache` (`initialize_brin_insertstate`, line 319). [verified-by-code, brin.c:319-334]
2. Compute `heapBlk = (origHeapBlk / pagesPerRange) * pagesPerRange` — the first block of this row's page range. [verified-by-code, brin.c:381-382]
3. **Autosummarize check**: if the row is the *first* row on the *first* page of a non-zero range, request `AVW_BRINSummarizeRange` for the *previous* range via `AutoVacuumRequestWork`. [verified-by-code, brin.c:398-425]
4. `brinGetTupleForHeapBlock` → fetch the summary tuple under `BUFFER_LOCK_SHARE`. If absent → range is unsummarized → return. [verified-by-code, brin.c:427-432]
5. Deform, call `add_values_to_range` (the opclass `consistent`/`addValue` dispatcher). If consistent, release share lock and exit. [verified-by-code, brin.c:443-454]
6. If expansion needed: snapshot the original tuple, build the new one, decide `samepage`, drop the share lock, call `brin_doupdate` (in `brin_pageops.c`) under exclusive lock. On retry/restart loop back. [verified-by-code, brin.c:455-501]

`brininsert` **always returns false** (no uniqueness reporting). [verified-by-code, brin.c:510]

## Scan path (`bringetbitmap`)

1. Open the heap to learn `nblocks` (needed because the revmap covers up to current heap end). [verified-by-code, brin.c:606-609]
2. Pre-allocate per-attribute scan-key arrays (regular + null-keys). [verified-by-code, brin.c:611-672]
3. Loop `heapBlk = 0; heapBlk < nblocks; heapBlk += pagesPerRange`:
   - Fetch summary tuple via `brinGetTupleForHeapBlock`.
   - If revmap entry is invalid → range unsummarized → **add every page in the range to the TIDBitmap unconditionally**.
   - Else deform, run per-attribute `consistent` proc, AND across attributes; if match → add the range; else skip.
4. Returns total page count for selectivity stats. [verified-by-code, brin.c:572-960]

A `per-range` AllocSet (`perRangeCxt`) is reset each iteration to bound memory. [verified-by-code, brin.c:~890]

## Build path (`brinbuild`)

`brinbuild` (1110) chooses serial vs parallel based on `RelationGetParallelWorkers`. Parallel path goes through `_brin_begin_parallel` → leader launches workers that each scan a heap range and emit summary tuples into a `Tuplesort`; leader then merges and inserts (`_brin_parallel_merge`, `_brin_parallel_scan_and_build`). Buildstate uses `brinbuildCallback` (1000) (serial) or `brinbuildCallbackParallel` (1051) (which dumps to tuplesort instead of inserting directly). [verified-by-code, brin.c:1110-1278]

`brinbuildempty` (1279) writes a metapage to the init fork via `smgr_bulk_*`.

## VACUUM path

- `brinbulkdelete` (1308): nearly a no-op — returns null stats. Intentional, since the index stores no heap TIDs. [verified-by-code, brin.c:1308-1322]
- `brinvacuumcleanup` (1323): scans the regular index pages via `brin_vacuum_scan` (2174), feeding each block's `PageGetFreeSpace` back into the FSM so future inserts can re-use space freed by tuple updates. [verified-by-code, brin.c:1323-1352]

## SQL-callable summarization

- `brin_summarize_new_values(regclass)` (1371) → wraps `brin_summarize_range(regclass, BRIN_ALL_BLOCKRANGES)`.
- `brin_summarize_range(regclass, blockrange)` (1386) → acquires `ShareUpdateExclusiveLock` on the index, calls `brinsummarize` over either all ranges or one specific range. [verified-by-code, brin.c:1386-1495]
- `brin_desummarize_range(regclass, blockno)` (1496) → invalidates a single range's revmap entry and frees its summary tuple. [verified-by-code]

## Parallel build coordination

`BrinShared` (lines 60-112) lives in DSM, holds a `ConditionVariable workersdonecv` + `slock_t mutex`. Workers each materialize summaries to a parallel `Tuplesort`; the leader waits on the CV, merges, and emits the final tuples. [verified-by-code, brin.c:60-112]

## Locking notes [HIGH-RISK SECTION]

- **Revmap lookup holds metapage in share mode briefly** in `brinRevmapInitialize`, then drops it; thereafter the revmap struct caches `lastRevmapPage`. [verified-by-code, brin_revmap.c:78-91]
- **Insert lock order**: `BUFFER_LOCK_SHARE` on the summary's regular page → drop → `BUFFER_LOCK_EXCLUSIVE` re-acquire inside `brin_doupdate` (after deciding `samepage`). The window between drop and re-acquire is why `brin_doupdate` *re-checks* that the old tuple is unchanged (`brin_pageops.c:115-164`). [verified-by-code, brin.c:480 + brin_pageops.c:108-164]
- **Cross-page update lock order**: old buffer + new buffer + revmap buffer. `brin_getinsertbuffer` (`brin_pageops.c`) deals with the buffer-pair locking. Order is "lowest block number first" to avoid deadlock — see `brin_pageops.c` (unverified that the comment explicitly states this rule, but `brin_getinsertbuffer` enforces it). [inferred]
- **`brininsert` may abandon and restart its top-level loop** if `brin_doupdate` returns false, because the revmap may have been re-pointed by a concurrent updater. [verified-by-code, brin.c:490-497]

## Cross-references

- **Called by:** `access/index/indexam.c` via `IndexAmRoutine` slots; `commands/vacuum.c`.
- **Calls into:** `brin_pageops.c` (`brin_doupdate`, `brin_can_do_samepage_update`), `brin_revmap.c` (`brinRevmapInitialize`, `brinGetTupleForHeapBlock`, `brinRevmapExtend`, `brinSetHeapBlockItemptr`), `brin_tuple.c` (`brin_form_tuple`, `brin_deform_tuple`, `brin_copy_tuple`, `brin_memtuple_initialize`), and per-opclass `addValue`/`consistent`/`union` via fmgr.

## Open questions

- Whether the `brin_can_do_samepage_update` window is closed correctly when *another* concurrent updater performs a cross-page update is asserted to be safe by the `brin_doupdate` re-check; the README does not formalize this. [unverified]
- Parallel build determinism: when two workers produce overlapping summaries for the same range, the merge in `_brin_parallel_merge` must combine via the opclass `union`. The exact code path was scanned but not deeply traced. [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/brin-summarize-and-scan.md](../../../../../idioms/brin-summarize-and-scan.md)

