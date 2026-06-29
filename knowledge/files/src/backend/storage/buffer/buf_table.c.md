# `src/backend/storage/buffer/buf_table.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~167
- **Source:** `source/src/backend/storage/buffer/buf_table.c`

Thin wrapper around the shared-memory `HTAB` that maps `BufferTag →
buf_id`. Caller-locked — every function asserts in its header comment
that the appropriate `BufMappingLock` partition is held; the
file's own functions do no locking. [verified-by-code]

## API / entry points

- `BufTableShmemCallbacks = { .request_fn = BufTableShmemRequest }` —
  registered as a shmem callback set; no `.init_fn` because an empty
  hash table needs no init (lines 38-41). [verified-by-code]
- `BufTableShmemRequest(void *arg)` (static) — requests a partitioned
  `HASH_FIXED_SIZE` shmem hash sized for `NBuffers + NUM_BUFFER_PARTITIONS`
  entries (lines 47-72). The +`NUM_BUFFER_PARTITIONS` slack is the
  documented concurrency cushion: `BufferAlloc` inserts the new entry
  *before* removing the old one, so per-partition each concurrent
  insertion can transiently hold two slots. [from-comment]
- `BufTableHashCode(BufferTag *tagPtr)` — one-shot hash of a tag.
  Exposed because callers need the hash before lookup to compute
  which `BufMappingLock` partition to acquire (lines 75-87). Doing it
  twice would double the `hash_any` cost. [verified-by-code]
- `BufTableLookup(tagPtr, hashcode)` — return `buf_id` or `-1`.
  Requires (at least) share lock on the partition's `BufMappingLock`
  (line 93). [verified-by-code]
- `BufTableInsert(tagPtr, hashcode, buf_id)` — insert if absent;
  return `-1` on success, or the colliding existing `buf_id` on
  conflict. Asserts `buf_id >= 0` and `tagPtr->blockNum != P_NEW`
  (lines 129-130). Requires *exclusive* partition lock. [verified-by-code]
- `BufTableDelete(tagPtr, hashcode)` — erase. `elog(ERROR, "shared buffer
  hash table corrupted")` if the entry isn't there (lines 165-166).
  Requires exclusive partition lock. [verified-by-code]

## Notable invariants / details

- `BufferLookupEnt` is the actual hash entry: `{BufferTag key; int id;}`
  (lines 28-32). The `id` is the index into `BufferDescriptors[]`.
  [verified-by-code]
- Caller-supplied locking is essential: the comment at line 6-10 spells
  out *why* — most callers need to mutate the `BufferDesc` while still
  holding the partition lock to maintain the lookup-table-and-header
  consistency invariant. Pushing the lock into these functions would
  force a release/re-acquire that breaks atomicity. [from-comment]
- `HASH_FIXED_SIZE` flag (line 70) means the hash never grows past the
  requested size; combined with the `+ NUM_BUFFER_PARTITIONS` slack
  this is the bound on transient over-occupancy. [verified-by-code]
- `HASH_PARTITION` flag (line 70) makes `hash_search_with_hash_value`
  multi-partition aware so concurrent reads/writes on different
  partitions don't contend a single freelist. [verified-by-code]
- `HASH_BLOBS` (line 70) tells `dynahash.c` to compare keys with `memcmp`
  rather than via a custom comparator — `BufferTag` is a flat POD with
  no padding holes in the layouts that matter. [verified-by-code]
- `BufTableInsert` returns `-1` on success (not the new `buf_id`),
  matching the "lookup returns -1 for not-in-table" convention. Callers
  in `bufmgr.c` rely on `result == -1` as "I won the race". The asymmetry
  with `BufTableLookup`'s "-1 means not found" is subtle but the test in
  `BufferAlloc` reads as `if (existing_buf_id >= 0) /* collision */`,
  which works for both. [verified-by-code]
- "Shared buffer hash table corrupted" in `BufTableDelete` (line 166)
  fires only if the buffer's tag was already removed by another path
  while we held the exclusive lock — a logic bug elsewhere. This is the
  "should never happen" assertion-as-error. [verified-by-code]

## Potential issues

- Line 60. `+ NUM_BUFFER_PARTITIONS` slack is a heuristic upper bound on
  in-flight `BufferAlloc` calls per partition; comment says "In principle
  this could be happening in each partition concurrently". This is an
  *upper bound on transient overcommit*, not a per-partition reservation,
  so a pathological workload that monopolises one partition could
  theoretically need more — but `BufferAlloc` would fall back to
  the clock sweep on insert failure, so this is a quality issue rather
  than correctness. [ISSUE-undocumented-invariant: NBuffers + NUM_BUFFER_PARTITIONS
  is a global cushion shared across partitions; pathological skew not
  bounded (nit)]
- Lines 84-87. `get_hash_value` is called twice for any
  lookup-then-insert sequence in `BufferAlloc` if the lookup misses
  (once here, once inside the actual insert) — but `hash_search_with_hash_value`
  takes the precomputed hash so the second `BufTableHashCode` call is
  *not* made by the caller; the file's hint about `hash_any` being slow
  is only relevant to one-shot callers. [verified-by-code]
- The header comment at line 1-10 is the only documentation of the
  caller-locking contract; the per-function comments restate it but the
  *which* `BufMappingLock` (partition vs single) only appears as
  "for tag's partition" — a reader has to know that
  `BufMappingPartitionLock(hashcode)` is the way to translate. Not a bug,
  just sparse. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `storage-buffer`](../../../../../issues/storage-buffer.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/buffertag.md](../../../../../data-structures/buffertag.md)
