# contrib/bloom/blscan.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 191
**Verification depth:** full read

## Role

Implements bloom index scans — bloom is bitmap-only (no `amgettuple`,
only `amgetbitmap`), so `blgetbitmap` is the workhorse: it reads every
data page of the index, intersects each tuple signature with the search
signature, and adds matching TIDs to a `TIDBitmap`.
[verified-by-code] `source/contrib/bloom/blscan.c:1-12`

## Public API

- `blbeginscan`, `blrescan`, `blendscan` — allocate / reset / free
  the `BloomScanOpaqueData`.
- `blgetbitmap(scan, tbm) → int64` — returns count of TIDs added.
  [verified-by-code] `source/contrib/bloom/blscan.c:26-71, 76-190`

## Invariants

- INV-1: NULL scan keys → zero matches; the AM `amsearchnulls=false`
  in blutils means NULL keys should never be passed, but if they are
  (defensive code path), the routine bails out with 0.
  [verified-by-code] `source/contrib/bloom/blscan.c:101-106`
- INV-2: Signature of the SCAN is built ONCE per scan (cached in
  `so->sign`) and reused for every block read. Rescan frees
  `so->sign` and the next `blgetbitmap` rebuilds it from the new
  keys.
  [verified-by-code] `source/contrib/bloom/blscan.c:46-58, 88-114`
- INV-3: All data blocks are read, never the metapage — loop runs
  `[BLOOM_HEAD_BLKNO, npages)`.
  [verified-by-code] `source/contrib/bloom/blscan.c:126-143`
- INV-4: Per-tuple match check is `(itup->sign[i] & so->sign[i]) ==
  so->sign[i]` for every word — i.e. all "search" bits must be set
  in the indexed signature. This is the bloom-filter
  superset-containment test.
  [verified-by-code] `source/contrib/bloom/blscan.c:162-170`
- INV-5: Match adds `&itup->heapPtr` to the bitmap with `recheck=true`
  — bloom matches are LOSSY (false positives expected).
  [verified-by-code] `source/contrib/bloom/blscan.c:173-176`

## Notable internals

- **Streaming reads** via `read_stream_begin_relation(READ_STREAM_FULL |
  READ_STREAM_USE_BATCHING, BAS_BULKREAD, ...)` — bloom scan is
  whole-index, so it benefits from prefetch.
  [verified-by-code] `source/contrib/bloom/blscan.c:120-141`
- **CHECK_FOR_INTERRUPTS** placed after every block — bounded by the
  block-scan rate.
  [verified-by-code] `source/contrib/bloom/blscan.c:182`
- `pgstat_count_index_scan(scan->indexRelation)` and
  `scan->instrument->nsearches++` for stats/EXPLAIN.
  [verified-by-code] `source/contrib/bloom/blscan.c:122-124`

## Trust-boundary / Phase-D surface

- **`recheck=true` is the safety net** — every bloom hit must be
  validated by the executor against the actual heap tuple. So even if
  an attacker crafts signature-colliding values, they can't get a row
  that *doesn't satisfy the predicate* returned to the client.
  Inherent to the AM.
- **All scanned pages held under BUFFER_LOCK_SHARE only** — no
  blocking of writers (except per-page).  No deadlock paths within
  the scan itself.
  [verified-by-code] `source/contrib/bloom/blscan.c:149`
- **Per-scan signature allocation** uses `palloc0_array` — zero-init,
  so any AND-fold against an attacker-influenced page reads only
  legitimate bits.
- **No timing leak via signature length** — `bloomLength` is per-index,
  fixed at creation, not attacker-tunable per scan.

## Cross-refs

- `source/src/backend/storage/aio/read_stream.c` — streaming-read API.
- `source/src/backend/access/gin/ginget.c` — sibling lossy bitmap AM.
- `source/src/backend/nodes/tidbitmap.c` — `tbm_add_tuples`.

## Issues raised

None — scan path is straight-forward and the recheck flag closes the
correctness gap.
