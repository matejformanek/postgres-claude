# dynahash + HASHCTL — the in-tree hashtable primitive

`dynahash` is PostgreSQL's general-purpose hashtable. Used
everywhere that needs O(1) lookup by key — buffer mapping, lock
manager partitions, syscache, plancache, lock-acquire local
state, statistics accumulators, type-cast registry. The
`HASHCTL` struct + `hash_create` flag set is the configuration
surface; once created, `hash_search` is the unified
insert/find/remove primitive.

Anchors:
- `source/src/include/utils/hsearch.h:64-103` — `HASHCTL` +
  flag bits [verified-by-code]
- `source/src/include/utils/hsearch.h:127-134` — primary API
- `source/src/backend/utils/hash/dynahash.c` — implementation
- `knowledge/data-structures/buffertag.md` — used as
  buffer-mapping key

## The HASHCTL struct

[verified-by-code `hsearch.h:64-84`]

```c
typedef struct HASHCTL
{
    int64        num_partitions;    /* HASH_PARTITION */
    Size         keysize;           /* HASH_ELEM (required) */
    Size         entrysize;         /* HASH_ELEM (required) */
    HashValueFunc hash;             /* HASH_FUNCTION */
    HashCompareFunc match;          /* HASH_COMPARE */
    HashCopyFunc keycopy;           /* HASH_KEYCOPY */
    HashAllocFunc alloc;            /* HASH_ALLOC */
    void        *alloc_arg;
    MemoryContext hcxt;             /* HASH_CONTEXT */
    HASHHDR     *hctl;              /* HASH_ATTACH */
} HASHCTL;
```

The struct is **fill-in-what-you-need**. Only the fields
indicated by the matching flag bit need be set.

`HASH_ELEM` (set keysize + entrysize) is **required** since
recent PG versions; the rest are optional.

## The flag bits

[verified-by-code `hsearch.h:86-101`]

| Flag | What it enables |
|---|---|
| `HASH_PARTITION` | Partitioned locking (num_partitions field, must be power of 2) |
| `HASH_ELEM` | keysize + entrysize (REQUIRED) |
| `HASH_STRINGS` | C-string keys (uses string_hash + strcmp) |
| `HASH_BLOBS` | Binary keys (uses tag_hash + memcmp) |
| `HASH_FUNCTION` | Custom hash function |
| `HASH_COMPARE` | Custom key comparison |
| `HASH_KEYCOPY` | Custom key copy (default: memcpy) |
| `HASH_ALLOC` | Custom allocator (default: MemoryContext palloc) |
| `HASH_CONTEXT` | Place entries in specific MemoryContext |
| `HASH_SHARED_MEM` | Live in shared memory (vs per-backend) |
| `HASH_ATTACH` | Don't initialize; attach to existing HASHHDR |
| `HASH_FIXED_SIZE` | nelem is hard cap; OOM if exceeded |

The flag-driven configuration model means you can build a
local backend hashtable with just `HASH_ELEM` + `HASH_BLOBS`,
or a heavily-customized shared-memory partitioned table with
`HASH_PARTITION | HASH_SHARED_MEM | HASH_ELEM | HASH_BLOBS`.

## The two key-handling shortcuts

- **`HASH_STRINGS`** — for `char *` keys. Uses `string_hash`
  for hashing and `strcmp` for comparison. Common for
  GUC tables, function-name caches.
- **`HASH_BLOBS`** — for fixed-size binary keys (the standard
  case). Uses `tag_hash` (FNV-derived) and `memcmp`. Used by
  buffer mapping, lock-table partitions, syscache.

For more exotic keys (tagged unions, multi-field structs with
care about pad bytes), use `HASH_FUNCTION` + `HASH_COMPARE`
explicitly.

## Creation

```c
HASHCTL info = {
    .keysize   = sizeof(MyKey),
    .entrysize = sizeof(MyEntry),
};
HTAB *table = hash_create("mytable", initial_nelem,
                          &info, HASH_ELEM | HASH_BLOBS);
```

[verified-by-code `hsearch.h:127-128`]

`initial_nelem` is a hint for sizing; the table grows
dynamically unless `HASH_FIXED_SIZE` is set.

## The four operations

```c
extern void *hash_search(HTAB *hashp, const void *keyPtr,
                         HASHACTION action, bool *foundPtr);
```

Where `action` is one of:

| HASHACTION | Behavior |
|---|---|
| `HASH_FIND` | Look up; return entry or NULL |
| `HASH_ENTER` | Look up; create if absent; ERROR on OOM |
| `HASH_ENTER_NULL` | Like ENTER but return NULL on OOM (no ERROR) |
| `HASH_REMOVE` | Look up; remove if found; return removed entry pointer (caller's last access) |

The returned pointer is to the **full entry** (including the
embedded key). The caller can read or write any fields. The
hashtable owns the storage until `HASH_REMOVE` or `hash_destroy`.

## The `foundPtr` distinguishes new vs existing

For `HASH_ENTER` / `HASH_ENTER_NULL`, the optional `foundPtr`
output tells whether the entry was **just created** (false)
or **already present** (true). Use it to discriminate
"initialize a fresh entry" vs "use an existing one":

```c
bool found;
MyEntry *entry = hash_search(table, &key, HASH_ENTER, &found);
if (!found)
    initialize_entry(entry);   /* fresh: must fill */
```

## hash_search_with_hash_value — pre-computed hash

[verified-by-code `hsearch.h:134-135`]

If you've already computed the hash value for some reason
(e.g. you're using the same key in multiple tables), call
`hash_search_with_hash_value` to skip re-hashing. Used by
the lock manager to share hash computation between LOCALLOCK
and shared lock-table lookups.

## Partitioned hashtables

`HASH_PARTITION` divides the hashtable into N independent
buckets, each protected by its own LWLock. Used for the
buffer-mapping table (16 partitions by default) and the
lock-manager table (16 partitions). Hash-then-partition:

```c
uint32 hash = get_hash_value(table, key);
LWLock *part_lock = MyPartitionLockFor(hash);
LWLockAcquire(part_lock, LW_EXCLUSIVE);
entry = hash_search_with_hash_value(table, key, hash, action, ...);
LWLockRelease(part_lock);
```

The partition count must be a power of 2; partition index =
hash mod N.

## Iteration

```c
HASH_SEQ_STATUS status;
hash_seq_init(&status, table);
while ((entry = hash_seq_search(&status)) != NULL)
    /* process entry */;
```

Sequential scan. **Not thread-safe** against concurrent
inserts; for shared-memory tables, hold the partition lock
during the seq scan.

## Memory model

- **Per-backend table** (default) — entries live in the
  context specified by `HASH_CONTEXT` or `TopMemoryContext`
  by default.
- **Shared-memory table** (`HASH_SHARED_MEM`) — entries
  live in shared memory. Must size with
  `ShmemInitHash` / similar; allocations come from a
  shmem allocator.

`HASH_ATTACH` is for the secondary backend joining a
shared table that another backend created — skip init.

## Common review-time concerns

- **`HASH_ELEM` is now required.** Older code may omit it
  with default values; new code must specify.
- **`HASH_BLOBS` keys must have no padding bytes** — same
  rule as BufferTag (hashed via memcmp + tag_hash).
- **`HASH_REMOVE` invalidates the returned pointer** after
  the next hash operation; copy the data first if needed.
- **Shared-memory tables can't shrink** — once entries are
  added, the underlying memory stays allocated.
- **Per-backend tables are reset on backend exit** — no
  cleanup needed at process exit.

## Invariants

- **[INV-1]** `HASH_ELEM` (keysize + entrysize) is required.
- **[INV-2]** Keys for `HASH_BLOBS` must have no padding
  bytes.
- **[INV-3]** Partitioned tables: partition count is a
  power of 2; partition index = hash mod count.
- **[INV-4]** `HASH_REMOVE`'s returned pointer is the
  caller's LAST access; don't store it.
- **[INV-5]** Shared-mem tables (`HASH_SHARED_MEM`) cannot
  shrink; size for peak.

## Useful greps

- All hash_create call sites:
  `grep -RIn 'hash_create' source/src/backend | wc -l`
- HASH_PARTITION users:
  `grep -RIn 'HASH_PARTITION' source/src/backend | head -10`
- HASH_BLOBS canonical patterns:
  `grep -RIn 'HASH_BLOBS' source/src/backend | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/hash/dynahash.c`](../files/src/backend/utils/hash/dynahash.c.md) | — | implementation |
| [`src/include/utils/hsearch.h`](../files/src/include/utils/hsearch.md) | 64 | HASHCTL + flag bits |
| [`src/include/utils/hsearch.h`](../files/src/include/utils/hsearch.md) | 127 | primary API |
| [`src/include/utils/hsearch.h`](../files/src/include/utils/hsearch.md) | — | public API |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/data-structures/buffertag.md` — buffer-mapping
  hashtable key.
- `knowledge/data-structures/locallock.md` — LOCALLOCK hash
  uses dynahash.
- `knowledge/idioms/cache-invalidation-registration.md` —
  syscache + relcache are dynahash tables.
- `.claude/skills/memory-contexts/SKILL.md` — `HASH_CONTEXT`
  lifetime choice.
- `.claude/skills/locking/SKILL.md` — partitioned-table
  LWLock pattern.
- `source/src/include/utils/hsearch.h` — public API.
- `source/src/backend/utils/hash/dynahash.c` —
  implementation.
