# hashovfl.c

- **Source path:** `source/src/backend/access/hash/hashovfl.c` (1129 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Overflow-page management: allocate / free overflow pages, maintain the bitmap pages, and the bucket-compact ("squeeze") helper. [from-comment, hashovfl.c:1-15]

## Key functions

| Function | Role |
|---|---|
| `_hash_addovflpage` | The allocator. Scans bitmap pages for a free bit; if none, extends index. Emits `XLOG_HASH_ADD_OVFL_PAGE` |
| `_hash_freeovflpage` | The deallocator. Moves tuples to earlier page (atomically with delink), updates bitmap, may update `hashm_firstfree` |
| `_hash_initbitmapbuffer` | Initialize a bitmap page (all-zero contents) |
| `_hash_firstfreebit` (static) | bit-twiddling: find first zero bit in a uint32 |
| `_hash_squeezebucket` | Walk bucket chain end-to-front, moving tuples from later pages into earlier ones to reclaim overflow pages |
| `_hash_get_oldblock_from_newbucket` | Compute the source bucket for a split-created bucket |

## Bitmap arithmetic

`hashm_spares[]` lets us compute, for any bit number, which bitmap page contains it and at what offset. Bit number `i` is in bitmap page #`i / BMPG_BITS_PER_PAGE`, offset `i % BMPG_BITS_PER_PAGE`. The first bit (#0) is the first bitmap page itself — "each bitmap page's first bit represents itself." [from-README, README:127-139]

## Locking [HIGH-RISK]

### Allocation (`_hash_addovflpage`)

Per README §"Free Space Management" pseudocode (lines 465-490):
1. Metapage exclusive lock.
2. Determine candidate bitmap page #.
3. **Release metapage** (to not hold it across the bitmap I/O).
4. Pin + exclusive-lock bitmap page.
5. Find a free bit; if found: set bit, mark dirty.
6. Re-acquire metapage exclusive lock; update `hashm_firstfree` if changed.
7. Else loop to next bitmap page.
8. If all checked: extend index, allocate new overflow page, update metapage.

### Free (`_hash_freeovflpage`)

Must hold bucket cleanup-lock (caller's responsibility; held by VACUUM/squeeze).
1. Move tuples out of the overflow page to an earlier page **atomically with the delink** to avoid standby seeing tuple twice. [from-README, README:558-561]
2. Update `(hasho_prevblkno, hasho_nextblkno)` on siblings to bypass the freed page.
3. Pin metapage (share), find bitmap-bit position, release metapage.
4. Pin bitmap (excl), then re-acquire metapage (excl).
5. **Clear bitmap bit BEFORE updating `hashm_firstfree`** — `firstfree` may legitimately underestimate (cost = next allocator scans more bits); must never overestimate (free page would be unreachable). [from-README, README:550-556]

## WAL records emitted

- `XLOG_HASH_ADD_OVFL_PAGE` — 4 blocks: new ovfl page, prev-last page (chain update), bitmap page (bit set), metapage.

## Cross-references

- **Called from:** `hashinsert.c::_hash_doinsert`, `hashpage.c::_hash_splitbucket`, `hash.c::hashbulkdelete`.

Tags: [from-README, README:454-560]; [verified-by-code for sequencing].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
