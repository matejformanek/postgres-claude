# `src/backend/lib/dshash.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1140
- **Source:** `source/src/backend/lib/dshash.c`

Concurrent open-addressed (well, open-chained — linked list per
bucket) hash table backed by a DSA segment. Used by pgstat shared
memory (`pgstat_shmem.c`), the typcache shared-state machinery,
and several extensions and infra (e.g. logical replication launcher's
worker tables). [verified-by-code §dshash.c:1-30]

The two interesting design choices: (a) a fixed set of 128 LWLock
partitions (`DSHASH_NUM_PARTITIONS_LOG2 = 7`), matching
`NUM_BUFFER_PARTITIONS` on the assumption "whatever's good for the
buffer pool is good enough"; (b) growth-only resize, geometric (doubles
the bucket count each time), which acquires ALL partition locks for the
duration of a resize — expensive but expected to happen only a small
number of times until the table stabilises. [from-comment §dshash.c:13-21, 56-62]

## API / entry points

- `dshash_create(area, params, arg)` — creates the control object and
  initial 128-bucket array in DSM, returns a backend-local handle.
  Initial size matches the partition count exactly so each partition
  starts with one bucket. [verified-by-code §dshash.c:209-266]
- `dshash_attach(area, params, handle, arg)` — attach in another
  backend; `buckets` pointer is lazy-resolved on first lookup via
  `ensure_valid_bucket_pointers()`. [verified-by-code §dshash.c:273-302]
- `dshash_detach(table)` — backend-local cleanup; the table itself
  persists in DSM. Asserts no partition locks held by me.
  [verified-by-code §dshash.c:311-317]
- `dshash_destroy(table)` — free every item and the control block;
  caller must guarantee no other backend will touch the table. Sets
  `magic = 0` to trip future asserts in stale attachers.
  [verified-by-code §dshash.c:327-364]
- `dshash_find(table, key, exclusive)` — returns entry pointer with
  the relevant partition LWLock held in the requested mode, or NULL.
  Caller MUST call `dshash_release_lock` to release.
  [verified-by-code §dshash.c:393-424]
- `dshash_find_or_insert_extended(table, key, *found, flags)` — same
  contract; always returns with exclusive lock. May trigger an
  in-line resize via the `restart:` goto when load factor > 0.75
  (= 1/2 + 1/4). Supports `DSHASH_INSERT_NO_OOM` to return NULL
  instead of `ereport(ERROR)` on DSA OOM. [verified-by-code §dshash.c:441-514, 134-139]
- `dshash_delete_key` / `dshash_delete_entry` / `dshash_release_lock`.
- `dshash_seq_init` / `dshash_seq_next` / `dshash_seq_term` / `dshash_delete_current`
  — sequential scan; iterates in partition order so locks can be
  handed off forward without deadlock vs resize.
  [verified-by-code §dshash.c:658-792]
- Convenience hash/cmp/copy: `dshash_memcmp`, `dshash_memhash`,
  `dshash_memcpy`, `dshash_strcmp`, `dshash_strhash`, `dshash_strcpy`.

## Notable invariants / details

- **Partition selection:** uses the HIGH bits of the hash for the
  partition, LOW(er) bits for the bucket — so resizing (which reveals
  more low bits) doesn't cross partition boundaries.
  [verified-by-code §dshash.c:141-160]
- **Lock-ordering for resize:** `resize()` acquires partition locks in
  ascending order (0..127) and `dshash_seq_next` matches that order,
  so the scan can't deadlock against a concurrent resize.
  [from-comment §dshash.c:732-738]
- **Load-factor knowledge per partition only:** there's no global
  count. Resize is triggered when one partition exceeds 0.75 average
  bucket fill; the comment notes "we just assume that this partition
  is representative" to avoid a central counter contention point.
  [from-comment §dshash.c:476-483]
- **DSHASH_MAGIC = 0x75ff6a20:** every public entry asserts it; on
  destroy it's set to 0 so use-after-destroy trips quickly in assert
  builds. [verified-by-code §dshash.c:64-66, 332, 357]
- **No shrink.** The header comment explicitly says "Currently, only
  growing is supported: the hash table never becomes smaller."
  [from-comment §dshash.c:8-9]
- **No iterators on stable order:** the seq-scan APIs hold a partition
  lock the entire time per partition, so they implicitly serialize
  against mutators of that partition but allow concurrent operations
  on other partitions. Read carefully — the scan IS NOT a snapshot.
  [inferred §dshash.c:677-760]
- **Interrupts are HELD across the LWLock-held entry pointer return.**
  The `dshash_find` comment hammers on this: "It is a very good idea
  for the caller to release the lock quickly." Practical implication
  for hot pgstat lookups: don't do palloc-heavy work between
  `dshash_find` and `dshash_release_lock`. [from-comment §dshash.c:386-391]

## Potential issues

- **File-line `dshash.c:71-74`.** Comment "We might want to add padding
  here so that each partition is on a different cache line, but doing
  so would bloat this structure considerably." — `dshash_partition` is
  `{ LWLock lock; size_t count; }` (~24 bytes on 64-bit), so 128 of
  them is ~3 KB. Adding 64-byte cache-line padding would bring that
  to ~8 KB inside the shared control block. Still small, and false
  sharing between partitions on the per-partition `count` counter
  could matter for write-heavy tables. [ISSUE-question: revisit cache-line padding for partitions (maybe)]
- **File-line `dshash.c:8-9, 20-21`.** Comment "Future versions may
  support iterators and incremental resizing; for now the
  implementation is minimalist." That's been the state since the file
  was added (PG 11). Iterators were retro-fitted but incremental
  resize wasn't. [ISSUE-stale-todo: incremental resize promised, never landed (nit)]
- **File-line `dshash.c:868`.** `delete_item` reaches
  `Assert(false)` if `delete_item_from_bucket` returns false (meaning
  the item couldn't be found in its expected bucket). In a non-assert
  build, the partition count is left in a state that doesn't reflect
  the actual bucket contents and execution continues. The condition
  shouldn't be reachable (caller holds exclusive lock and we just
  validated the magic), but it's a silent corruption window if it
  ever triggers in production. [ISSUE-correctness: bucket/count drift if delete_item_from_bucket fails non-assert (maybe)]
