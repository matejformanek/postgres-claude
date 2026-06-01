# `src/common/blkreftable.c` (compiled into backend)

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1200
- **Source:** `source/src/common/blkreftable.c`

Note: this file lives in `src/common/` so it can also be used by
frontend tools (`pg_basebackup`, `pg_combinebackup`), but it is the
load-bearing data structure for the backend's WAL summarizer + the
incremental-backup feature. Documenting it here since the user's
task points at it under `backup/`.

## Purpose

A `BlockRefTable` records, per (RelFileLocator, ForkNumber), the set of
blocks that were modified within some WAL LSN range, plus the
**limit block** — the minimum known relation length over that range (0
if created/dropped, post-truncation length if truncated). When the
limit shrinks, blocks beyond it are forgotten (they no longer exist;
if the relation is later extended, those blocks count as freshly
modified). [from-comment] (`blkreftable.c:4-19`)

## Chunked dual representation

Each (rel, fork) is divided into chunks of `BLOCKS_PER_CHUNK = 65 536`
blocks (= 2^16). Each chunk independently uses one of two encodings:

- **Array**: when modified-block count in the chunk is small. Store
  `uint16` offsets-from-chunk-start. Initial capacity
  `INITIAL_ENTRIES_PER_CHUNK = 16`, doubles up to `MAX_ENTRIES_PER_CHUNK
  = BLOCKS_PER_CHUNK / 16 = 4096`.
- **Bitmap**: when array size would reach 4096, convert to a 64 KiB
  (`MAX_ENTRIES_PER_CHUNK * 2 = 8 KiB` = 65 536 bits) bitmap. Now grows
  no further — every block in the chunk gets a bit.

This is the same encoding **on disk and in memory** — the serialization
just streams chunks. So the format is naturally compact for both
"sparsely-modified large rel" and "almost-fully-modified rel" cases.
[from-comment] (`blkreftable.c:54-77`)

## Data structures

- `BlockRefTableEntry` (`blkreftable.c:110-119`): per (rlocator, forknum)
  state. Holds `limit_block`, three parallel arrays of length `nchunks`:
  `chunk_size[]` (allocated capacity in entries), `chunk_usage[]` (live
  count; equals `MAX_ENTRIES_PER_CHUNK` to flag "this is a bitmap"),
  `chunk_data[]` (pointer per chunk).
- `BlockRefTable` (`blkreftable.c:144-150`): simplehash over
  `BlockRefTableKey → Entry*`, optionally tagged with a MemoryContext
  in backend builds.
- Serialization unit `BlockRefTableSerializedEntry` (`blkreftable.c:155-161`)
  is a header followed by `nchunks` chunk-headers and bodies.

## Incremental read/write API

- Reader: `BlockRefTableReader` streams chunks from disk one at a time
  — never loads the whole table. `BlockRefTableReaderGetBlocks` yields
  block numbers, switching between array-iteration and bit-scan based
  on `chunk_usage`. Used by `pg_combinebackup` to know which blocks of
  an incremental backup contain real data vs. holes.
- Writer: `BlockRefTableWriter` accepts entries via
  `WriteBlockRefTableEntry`, buffers up to `BUFSIZE = 65 536` bytes,
  flushes via the user-supplied `io_callback`. Writes a CRC32C over
  the file as the trailer. (`blkreftable.c:166`, `:178`)

## Key operations

- `BlockRefTableSetLimitBlock(brtab, rlocator, forknum, limit)` — set
  the post-truncation length; forget any tracked blocks `>= limit`.
- `BlockRefTableMarkBlockModified(brtab, rlocator, forknum, blknum)` —
  add to the chunk's array or set the bit; promote array→bitmap if
  the array would exceed `MAX_ENTRIES_PER_CHUNK`.
- `BlockRefTableSerialize` / `BlockRefTableDeserialize` — full
  round-trip (used in tests; runtime path uses Reader/Writer
  incrementally).

## Notable invariants

- The same block being marked twice is a no-op (array path: dedup on
  insert; bitmap path: bit already set).
- An entry is **discarded entirely** when SetLimitBlock to 0 — the
  hash entry isn't even kept (relation dropped). [from-comment]
  (`blkreftable.c:16-19`)
- Backend allocates inside `BlockRefTable->mcxt`; frontend uses
  `pg_malloc0`. Same code, two allocators.

## Tag tally

`[verified-by-code]` 5 / `[from-comment]` 5
