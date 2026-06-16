---
path: src/common/blkreftable.c
anchor_sha: 4b0bf0788b0
loc: 1324
depth: surface
---

# blkreftable.c

- **Source path:** `source/src/common/blkreftable.c`
- **Lines:** 1324
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/blkreftable.h`, `src/bin/pg_combinebackup/*`, `src/backend/backup/basebackup_incremental.c`.

## Purpose

Block-reference table — the core data structure powering **incremental backups**. Server-side, a BRT is built during a WAL replay scan and serialized into a per-LSN-range file on disk (`<datadir>/global/pg_filenode.map`-adjacent, actually under `pg_wal/summaries/`). Client-side, `pg_combinebackup` reads BRT files for the LSN gaps between a chain of incremental backups and uses them to decide which blocks of each relation file to copy from which level. [from-comment, blkreftable.c:5-26]

## Role in PG

Both frontend (pg_combinebackup reads and merges BRTs) and backend (`basebackup_incremental.c` writes BRTs as part of `pg_basebackup --incremental`). The serialization format is the contract between writer and reader.

## Storage representation

- Per-relation-fork entry: `limit_block` (truncation watermark) + `nchunks` × ( `chunk_size`, `chunk_usage`, `chunk_data` ). Each chunk covers `BLOCKS_PER_CHUNK = 65536` consecutive blocks of the fork. [verified-by-code, blkreftable.c:78-119]
- A chunk is stored as either (a) sparse array of `uint16` offsets-within-chunk, or (b) when modified count grows past `MAX_ENTRIES_PER_CHUNK = 65536 / 16 = 4096`, a bitmap of 65536 bits = 4096 `uint16`s. The bitmap and the dense array are the same size, so once flipped to bitmap, no further growth. [verified-by-code, blkreftable.c:78-81,1086]
- In-memory entries live in a `simplehash` keyed by (rlocator, forknum). [verified-by-code, blkreftable.c:122-135]

## On-disk format

- `uint32 magic = BLOCKREFTABLE_MAGIC (0x652b137b)`. [verified-by-code, blkreftable.c:480-489]
- Repeated: `BlockRefTableSerializedEntry{rlocator, forknum, limit_block, nchunks}` + nchunks×`uint16` chunk_size array + raw chunk bodies in order. [verified-by-code, blkreftable.c:521-550]
- Sentinel: an all-zero `BlockRefTableSerializedEntry`. Then `uint32 CRC-32C` over everything from `magic` to (but not including) the CRC itself. [verified-by-code, blkreftable.c:1304-1324]
- The buffered I/O layer (`BlockRefTableBuffer`, BUFSIZE=64K) is the single CRC accumulator point. [verified-by-code, blkreftable.c:170-179,1208-1297]

## Key functions

- `CreateBlockRefTableReader(read_callback, …, error_filename, error_callback, …)` (576-604) — read first 4 bytes, check magic, return reader. [verified-by-code, blkreftable.c:576-604]
- `BlockRefTableReaderNextRelation(reader, …)` (612-690) — read next `BlockRefTableSerializedEntry`. **All-zero ⇒ sentinel ⇒ read+check CRC, return false.** Otherwise `nchunks > MaxAllocSize / sizeof(uint16)` ⇒ error. Otherwise `palloc_array(uint16, nchunks)` and read chunk-size array. [verified-by-code, blkreftable.c:612-690]
- `BlockRefTableReaderGetBlocks(reader, blocks, nblocks)` (702-…) — iterate over `total_chunks - consumed_chunks` chunks, decode array or bitmap, write into caller's `BlockNumber` array. [verified-by-code, blkreftable.c:702-…]
- `WriteBlockRefTable(brtab, write_callback, write_callback_arg)` (473-555) — in-memory hash → sorted serialized stream + sentinel + CRC. [verified-by-code, blkreftable.c:473-555]
- `BlockRefTableEntryMarkBlockModified` (978-…) — flip an array chunk to bitmap when it overflows `MAX_ENTRIES_PER_CHUNK`. [verified-by-code, blkreftable.c:978-1100, by structure]
- `BlockRefTableRead` (1208-1267) — bounded read loop; if direct read or buffer refill returns 0, call `error_callback("file ends unexpectedly")` (which is `noreturn`). [verified-by-code, blkreftable.c:1208-1267]

## State / globals

None (file-scope). All state lives on the `BlockRefTable` / `BlockRefTableReader` / `BlockRefTableWriter` structs.

## Phase D notes — hostile-BRT-file surface

This is the **central A3-shaped trust boundary**: pg_combinebackup reads BRT files from a backup directory the operator may not fully control. A hostile incremental-backup archive that ships a doctored BRT file gets one shot at the parser before pg_combinebackup decides what blocks to copy where.

- **Magic + trailing CRC are the only authentication.** A file with the correct 4-byte magic and any internally-consistent contents will be trusted. CRC-32C is not crypto; an attacker rewriting the BRT body also rewrites the CRC. [verified-by-code, blkreftable.c:595-601,652-655] [ISSUE-trust-boundary: blkreftable file is CRC-only; no signature/MAC; pg_combinebackup trusts whatever block list it produces (maybe-high — echoes pg_dump archive trust model)]
- **`nchunks` sanity check is `> MaxAllocSize / sizeof(uint16)`** (line 666) — prevents palloc-array overflow but does **NOT** prevent a chunks array large enough to consume gigabytes of frontend memory before failing other limits. A hostile BRT claiming `nchunks = 2^28` (just under `MaxAllocSize/2`) allocates 1 GiB for the chunk_size array alone. Per-entry; an attacker can include many entries. [verified-by-code, blkreftable.c:666-672] [ISSUE-dos: blkreftable parser accepts nchunks just under MaxAllocSize/2 ⇒ frontend memory blowup; no aggregate cap across entries (maybe)]
- **`limit_block` is fully attacker-controlled.** `BlockRefTableEntrySetLimitBlock` (908-…) accepts any `BlockNumber` and **truncates the in-memory chunk arrays accordingly**. A hostile file with `limit_block = 0` for a real relation effectively says "all blocks past the start are modified" — pg_combinebackup will then re-copy the entire relation from the source backup. That's a "make the operator copy more data" attack, not a corruption attack. The opposite — `limit_block = BlockNumberIsValid_max` and an empty chunk list — says "no blocks modified" which would cause **stale data** in the combined backup. [verified-by-code, blkreftable.c:907-…] [ISSUE-trust-boundary: limit_block from a hostile BRT controls which blocks pg_combinebackup considers modified — can silently drop blocks from the combined backup (maybe-high)]
- **Per-chunk bitmap is unbounded by `chunk_usage`.** When `nchunks` is large and each chunk is in bitmap mode (`chunk_usage[j] = MAX_ENTRIES_PER_CHUNK = 4096`), per-entry memory is `nchunks * 4096 * 2 = 8KB * nchunks`. With `nchunks = 1e6` that's 8 GiB. [verified-by-code, blkreftable.c:1086] [maybe — Phase D]
- **No bound on number of relation entries.** The reader processes them one at a time and accumulates per-relation pallocs (`reader->chunk_size`) which it `pfree`s before the next (line 675-676), so steady-state memory is one entry's worth. Good. [verified-by-code, blkreftable.c:675-679]
- **`BlockRefTableRead` reads via callback** (lines 1239, 1256). The callback is supplied by the caller and is expected to handle I/O errors via its own machinery (the comment at the header explicitly says I/O errors are not the parser's problem). [verified-by-code, blkreftable.c:570-572,1208-1267]
- **CRC is computed over data as we read it** (line 1225-1226, 1241), then the trailing 4 bytes are XOR-equiv-compared. The accumulator is snapshotted (line 645) before reading the CRC so the CRC computation itself doesn't perturb the value. Same idiom on the write side (1318). [verified-by-code, blkreftable.c:1208-1267,1318]
- **`BlockRefTableEntryGetBlocks` iterates respecting `start_blkno`/`stop_blkno`** with an explicit overflow guard at line 384-387. [verified-by-code, blkreftable.c:384-460]

## Cross-references

- `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md` — sister "trust the archive" pattern.
- pg_combinebackup driver: `src/bin/pg_combinebackup/*`.
- Server-side writer: `src/backend/backup/basebackup_incremental.c`.

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[from-comment]=2 [verified-by-code]=15 [maybe]=2 [ISSUE]=3`
