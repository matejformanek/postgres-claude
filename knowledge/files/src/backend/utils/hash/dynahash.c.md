# `src/backend/utils/hash/dynahash.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1911
- **Source:** `source/src/backend/utils/hash/dynahash.c`

## Purpose

Generic chained-bucket hash table used everywhere in PG: local per-backend
caches (relcache, catcache hooks, planner caches) AND all named shared-memory
hash tables (buffer mapping, lockmgr, predicate-lock, pgstat shmem index, …).
Supports dynamic expansion (Larson linear hashing) for local tables; shared
tables are fixed-directory at creation. [from-comment] (`dynahash.c:3-29`)

## Mental model

- **Bucket directory → segment → bucket → element chain.** Directory of
  pointers to segments of `HASH_SEGSIZE = 256` bucket heads; each bucket is
  a linked list of `HASHELEMENT`s. (`dynahash.c:108-127`)
- **Local vs shared.** Non-shared: full lifecycle in a private memory
  context, growable directory, palloc-style errors on OOM. Shared: HASHHDR
  lives in shmem, each backend has its own local `HTAB` struct, directory
  pointer fixed at creation, allocator must return NULL on OOM.
  [from-comment] (`dynahash.c:164-169`, `:25-29`)
- **Partitioned tables (`HASH_PARTITION`).** For high-concurrency shared
  tables (notably buffer mapping + lockmgr). Caller uses low bits of hash
  to pick a partition lock; dynahash promises that bucket assignment
  respects those low bits so each partition's buckets are disjoint. **No
  on-the-fly bucket splitting in partitioned mode** — `expand_table` is
  disabled, so `nelem` at creation must be accurate. [from-comment]
  (`dynahash.c:7-23`, `:184-191`)
- **NUM_FREELISTS = 32 freelists per HASHHDR**, each with its own spinlock
  and `nentries` counter, to reduce cache-line contention on free-list ops
  in shared tables. Unpartitioned tables use only `freeList[0]` and its
  spinlock is ignored. (`dynahash.c:129-130`, `:172-182`)
- **Pointer stability.** Entries never move (no rehashing-in-place), so
  callers can safely hold raw entry pointers across other lookups (within
  proper locking). One of dynahash's main advantages over simplehash.
  [from-comment] (`dynahash.c:46-54`)
- **Larson linear hashing.** `max_bucket`, `high_mask`, `low_mask` drive
  `calc_bucket` (`dynahash.c:852`); when load factor exceeded, one bucket
  splits at a time via `expand_table` (`dynahash.c:1481`).

## Spine

- `hash_create` (`dynahash.c:360`) — flags decode: `HASH_ELEM` mandatory,
  exactly one of `HASH_STRINGS | HASH_BLOBS | HASH_FUNCTION`,
  `HASH_PARTITION` chooses partitioned mode, `HASH_SHARED_MEM` chooses
  shared, `HASH_CONTEXT` overrides parent memory context.
- `hdefault` (`dynahash.c:630`) sets `dsize = DEF_DIRSIZE = 256`,
  `ffactor = 1`.
- `hash_search` / `hash_search_with_hash_value` (`dynahash.c:889`, `:902`) —
  unified `HASH_FIND | HASH_ENTER | HASH_REMOVE | HASH_ENTER_NULL` entry
  point. Find walks bucket chain by `match()` function; ENTER pulls from
  freelist via `get_hash_entry`; REMOVE unlinks and returns to freelist.
- `get_hash_entry` (`dynahash.c:1188`) — if local freelist empty: try
  `element_alloc` for a new batch; if that fails (partitioned shared
  table, no more room): **steal one entry from another freelist** under
  spinlock. This is why each freelist needs its own lock even though
  partitioning would otherwise suggest none.
- `expand_table` (`dynahash.c:1481`) — Larson split: increments
  `max_bucket`, walks the bucket being split, relinks each entry into
  either old or new bucket based on the now-exposed high bit. Never
  called for partitioned tables (Assert).
- `hash_seq_init` / `hash_seq_search` (`dynahash.c:1317`, `:1352`) — iterate
  all buckets; tracked in a backend-global registry so concurrent ENTER
  during seq scan can be detected (and bucket splits suppressed).
  `register_seq_scan` / `deregister_seq_scan`.
- `hash_freeze` (`dynahash.c:1464`) — local-only; lock the table read-only.

## Locking rules

- **Unpartitioned shared table:** single LWLock owned by the caller covers
  the entire table. SHARED for `HASH_FIND` / seq scans, EXCLUSIVE for
  `HASH_ENTER` / `HASH_REMOVE`. [from-comment] (`dynahash.c:6-15`)
- **Partitioned shared table:** caller's per-partition LWLock covers all
  ops on entries whose hash falls in that partition. Internally dynahash
  also takes the per-freelist spinlock during `get_hash_entry` /
  `hash_search REMOVE` for the freelist (which is keyed on hashcode mod 32,
  not by partition).
- **Freelist contention path:** `get_hash_entry` may scavenge from a
  freelist *other than* the hashcode's home freelist — this is why each
  freelist needs its own spinlock independent of caller's partition lock.
  [from-comment] (`dynahash.c:146-149`)

## Notable invariants

- `keysize > 0`, `entrysize >= keysize` (`dynahash.c:371-372`).
- Element memory layout: `HASHELEMENT` header then `MAXALIGN`-padded key
  + entry. `ELEMENTKEY(h)` / `ELEMENT_FROM_KEY(k)` macros (`dynahash.c:257-263`).
- For shared tables: `nelem` must be sized correctly up front; running out
  triggers freelist-stealing then ERROR. (`dynahash.c:353-358`)
- `HASH_STRINGS` uses `strncmp(keysize-1)` because keys are `strlcpy`'d.
  (`dynahash.c:313-317`)

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 10

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [data-structures/dynahash-hashctl.md](../../../../../data-structures/dynahash-hashctl.md)

