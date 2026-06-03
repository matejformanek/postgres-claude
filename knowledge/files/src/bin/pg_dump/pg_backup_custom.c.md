---
path: src/bin/pg_dump/pg_backup_custom.c
anchor_sha: 4b0bf0788b0
loc: 1032
depth: deep
---

# pg_backup_custom.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_custom.c`
- **Lines:** 1032
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_archiver.h` (BLK_* macros, K_OFFSET_*, `ArchiveHandle` slots populated here), `pg_backup_archiver.c` (ReadHead/WriteHead/ReadToc/WriteToc, `parallel_restore`, `ReadInt/WriteInt`), `compress_io.c`/`compress_io.h` (`AllocateCompressor`, `EndCompressor`, gzip/lz4/zstd unification).

## Purpose

Implements the **custom format (`-Fc`, the default)** — a single binary file with header, TOC, then a stream of compressed data blocks, each tagged with a block-type byte and the dumpId it belongs to. This file is the canonical "reference implementation" for writing a new format. [from-comment, pg_backup_custom.c:7-8]

The file is also a primary surface for **"attacker-controlled archive at superuser pg_restore"** because its parser walks length-prefixed data blocks from disk. Phase D should focus on `_readBlockHeader`, `_skipData`, `_CustomReadFunc`, and `ReadOffset`/`ReadInt` upstream.

## On-disk layout

```
"PGDMP"             5 magic bytes                       (WriteHead in archiver.c)
maj/min/rev         3 bytes (version)
intSize             1 byte
offSize             1 byte
format              1 byte
compression_algo    1 byte (since v1.15)
createDate          7 ints (sec,min,hour,mday,mon,year,isdst)
db / serverVer / dumpVer   3 length-prefixed strings
                    ─ end of header (archiver.c:4170-4193) ─

WriteInt(tocCount)
per TOC entry:      WriteInt(dumpId), WriteInt(hadDumper),
                    WriteStr(tableoid_str), WriteStr(oid_str),
                    WriteStr(tag), WriteStr(desc),
                    WriteInt(section),
                    WriteStr(defn) / WriteStr(dropStmt) / WriteStr(copyStmt) /
                    WriteStr(namespace) / WriteStr(tablespace) / WriteStr(tableam),
                    WriteInt(relkind),
                    WriteStr(owner), WriteStr("false"),
                    deps as strings terminated by WriteStr(NULL),
                    WriteExtraTocPtr → WriteOffset(dataPos, dataState)
                    ─ archiver.c:2632-2728 ─

data section (per TE with data):
    WriteByte(BLK_DATA=1) or WriteByte(BLK_BLOBS=3)
    WriteInt(te->dumpId)         ── sanity check ──
    [for BLOBS: WriteInt(loOid) repeated, terminated by WriteInt(0)]
    compressed data, written as repeated chunks of:
        WriteInt(blockLen)
        blockLen raw bytes
    WriteInt(0)                  ── end-of-data marker ──

[optional second pass: re-seek to TOC and rewrite to fill in dataPos]
EOF
```

[verified-by-code, pg_backup_custom.c:746-782; archiver.c:4170-4193]

## Public surface

Only `InitArchiveFmt_Custom(ArchiveHandle *AH)` (104). Populates 20+ function-pointer slots. Then either opens write mode (creates the file or uses stdout) or read mode (opens file, calls `ReadHead` and `ReadToc` to load the metadata, then records `lastFilePos` as the start of data blocks for later searches). [verified-by-code, pg_backup_custom.c:104-188]

## Key data structures

- `lclContext` (68-74) — per-archive state on `AH->formatData`:
  - `CompressorState *cs` — active compressor while writing.
  - `int hasSeek` — whether `fseeko`/`ftello` work (set by `checkSeek`).
  - `pgoff_t lastFilePos` — read-time, the position after the last data block scanned; used as a search start.
- `lclTocEntry` (76-80) — per-TocEntry state on `te->formatData`:
  - `int dataState` — `K_OFFSET_POS_NOT_SET / K_OFFSET_POS_SET / K_OFFSET_NO_DATA`.
  - `pgoff_t dataPos` — file offset of this entry's data block (only valid if `dataState == K_OFFSET_POS_SET`).

## Key functions

### Write path

- `_StartData` (283) — records current file position into `tctx->dataPos`/`dataState`, emits `BLK_DATA`, `WriteInt(dumpId)`, and starts a fresh compressor whose `writeData` calls back through `_CustomWriteFunc`. [verified-by-code, pg_backup_custom.c:283-299]
- `_WriteData` (310) — pushes raw bytes to the compressor (which buffers and eventually calls `_CustomWriteFunc`).
- `_EndData` (327) — `EndCompressor` flushes/closes the compressor, then `WriteInt(0)` writes the end-of-block marker.
- `_StartLOs` / `_StartLO` / `_EndLO` / `_EndLOs` (348-409) — similar but with `BLK_BLOBS` and per-LO OID framing; `_StartLO` pg_fatals on OID 0; `_EndLOs` writes a final `WriteInt(0)` as end-of-LOs marker.
- `_CustomWriteFunc` (995) — the compressor's data-out sink. For each chunk: `WriteInt(len); _WriteBuf(buf, len);`. Skips zero-length chunks. [verified-by-code, pg_backup_custom.c:995-1004]
- `_CloseArchive` (746) — emits header + TOC + data, then **re-seeks back and rewrites the TOC** to fill in data offsets (only if `hasSeek` and we actually dumped data). Then fsync if `dosync`. [verified-by-code, pg_backup_custom.c:746-782]

### Read path [Phase D primary surface]

- `_PrintTocData` (414-562) — Decision tree:
  - If `dataState == K_OFFSET_NO_DATA`, return.
  - If `!hasSeek` OR `dataState == K_OFFSET_POS_NOT_SET`: linear scan from `lastFilePos`, reading block headers and skipping `BLK_DATA`/`BLK_BLOBS` until `id == te->dumpId`. Records discovered offsets back into the other TEs' lclTocEntry as a side effect (with a thread-safety comment, see below). [verified-by-code, pg_backup_custom.c:425-501]
  - Else: `fseeko` to `tctx->dataPos`, read one block header.
  - If we hit EOF: pg_fatal with one of two messages — "out-of-order restore" or "corrupt archive" depending on `hasSeek`.
  - **Sanity check `id != te->dumpId` → pg_fatal**.
  - Switch on `blkType` — `BLK_DATA → _PrintData`, `BLK_BLOBS → _LoadLOs`, default → `pg_fatal("unrecognized data block type %d while restoring archive")`.
- `_readBlockHeader` (963-989) — read 1 byte for type, `ReadInt` for id. **Pre-1.3 archives: type is hardcoded to `BLK_DATA`**. EOF check for type byte but not for id; comment (969-974) says "no such files are likely to exist in the wild". [from-comment, pg_backup_custom.c:967-974; verified-by-code, pg_backup_custom.c:963-989]
- `_skipData` (621-665) — `ReadInt(blkLen)` then either `fseeko(blkLen, SEEK_CUR)` (if seekable + blkLen ≥ 4 KiB) or `fread(buf, blkLen, …)`. **Loop until `blkLen == 0`.** Allocates an unbounded buffer up to `blkLen` for non-seekable mode (line 650: `pg_malloc(buflen)`). [verified-by-code, pg_backup_custom.c:621-665]
- `_skipLOs` (603-614) — `ReadInt(oid)` loop, skipping each LO via `_skipData` until OID 0.
- `_LoadLOs` (578-595) — `ReadInt(oid)` loop, restoring each via `StartRestoreLO` + `_PrintData` + `EndRestoreLO`.
- `_CustomReadFunc` (1010-1032) — the compressor's data-in source: `ReadInt(blkLen)` (return 0 on end-marker), then realloc caller buffer if needed and `_ReadBuf(buf, blkLen)`. **This is the path where length-prefix overflow matters most.** [verified-by-code, pg_backup_custom.c:1010-1032]
- `_ReadByte` (691-700) — `getc(FH)`; pg_fatal on EOF.
- `_ReadBuf` (723-728) — `fread`; pg_fatal on short read.

### Parallel restore

- `_PrepParallelRestore` (836-883) — Reconstructs each TE's `dataLength` by `dataPos[i+1] - dataPos[i]` (deltas in the file). For the last TE: `SEEK_END` + `ftello`. This drives the size-sorted dispatch (big TEs first). [verified-by-code, pg_backup_custom.c:836-883]
- `_Clone` (888-910) — per-thread `lclContext` copy via `memcpy`. **Intentionally does NOT clone the per-TE `lclTocEntry` state** — threads share discovered offsets across the lclTocEntry (with the warning comment below). [from-comment, pg_backup_custom.c:903-909]
- `_DeClone` (912-918) — `free(ctx)`.
- `_ReopenArchive` (791-824) — close & reopen file on Unix, just record file pos on Windows. pg_fatals if `!hasSeek` or no fSpec.
- `_WorkerJobRestoreCustom` (924) — just calls `parallel_restore`.

## Concurrency note [the only race in this file]

In `_PrintTocData`, when a linear scan discovers a data block for some other TE and updates `othertctx->dataPos / dataState`:

> "Note: on Windows, multiple threads might access/update the same lclTocEntry concurrently, but that should be safe as long as we update dataPos before dataState. Ideally, we'd use pg_write_barrier() to enforce that, but the needed infrastructure doesn't exist in frontend code. But Windows only runs on machines with strong store ordering, so it should be okay for now."

[from-comment, pg_backup_custom.c:461-469]

That's the entire concurrency contract for parallel restore from a custom archive: relies on **x86 TSO** for ordering, no fence. If pg_dump ever runs on ARM/Windows this comment becomes critical.

## Phase D notes [attacker-controlled-archive at pg_restore]

This is the **highest-value surface** in the format-backend group: a custom archive consumed by superuser pg_restore.

- **`ReadInt` returns `int`, but is used as `size_t blkLen` in `_skipData` (line 629)** and `_CustomReadFunc` (1016). `blkLen = ReadInt(AH)` — implicit `int → size_t` widening. If the int is negative (`ReadInt` reads a sign byte, archiver.c:2196-2199), `blkLen` becomes a huge size_t. In `_CustomReadFunc` (1021): `if (blkLen > *buflen) free(*buf); *buf = pg_malloc(blkLen)` — `pg_malloc` of a near-`SIZE_MAX` value will pg_fatal cleanly, but a negative-looking-but-small value (e.g. `-1` → `(size_t)-1`) is rejected by malloc. **However**, a negative `blkLen` that happens to be a small `int` (e.g. archive emits `(sign=1, magnitude=4096)` → `ReadInt` returns `-4096`, cast to `size_t = 0xFFFFFFFFFFFFF000`) would also fail malloc. So pg_malloc is the saving wall. `[maybe — phase D]` — worth fuzzing.
- **`_skipData` non-seekable branch (646-651):** `buflen = Max(blkLen, 4 * 1024); buf = pg_malloc(buflen);` — same pg_malloc bound applies; OOM exits cleanly.
- **`_skipData` seekable branch (639-643):** `fseeko(AH->FH, blkLen, SEEK_CUR)`. `blkLen` is `size_t` widened from int; `fseeko` takes off_t. A negative-derived `blkLen` cast back into off_t may seek to a wild position. Subsequent `ReadInt(blkLen)` reads garbage; loop may take many iterations before EOF or pg_fatal. **DoS but not arbitrary memory.** `[maybe — phase D]`
- **`_readBlockHeader` does NOT validate `blkType` here** — only in `_PrintTocData`'s switch (485-499 and 533-547). If a corrupted file presents `BLK_DATA` but the data follows BLOBS framing, `_PrintData → cs->readData` reads garbage chunks until `WriteInt(0)` marker, no boundary check. `[maybe — phase D]`
- **`_PrintTocData` linear-scan trusts every block header it skips past** to record other TEs' offsets. A hostile archive can populate dataState/dataPos of arbitrary other TEs at chosen offsets. When pg_restore later visits one of those TEs, it `fseeko(dataPos)` and reads — effectively, the attacker controls "where pg_restore reads the next data from". Since it still gates by `id == te->dumpId` (line 449, 529), arbitrary offsets must still parse as a header tagged with the matching dumpId. Bounded by checksum-style discipline of `WriteInt(dumpId)` after BLK byte. `[maybe — phase D]` [verified-by-code, pg_backup_custom.c:455-481]
- **`fseeko(AH->FH, tpos, SEEK_SET)` on attacker-controlled `tpos`** is bounded by `pgoff_t` arithmetic but pg_restore performs no upper-bound check vs file size. Reading past EOF returns short reads, which trigger `pg_fatal` via `_ReadBuf` / READ_ERROR_EXIT. `[fine]`
- **Compression algorithm byte from header.** `AH->compression_spec.algorithm = AH->ReadBytePtr(AH)` (archiver.c:4253). If the byte is an unknown enum value, `supports_compression` returns an error message and pg_log_warning printed; `AllocateCompressor` will probably pg_fatal. Not a memory-safety hazard but a useful place to fuzz. `[maybe — phase D]`
- **`WriteInt(0)` end-of-block marker** — there is no length-cap on a single block. A pathological archive can encode one huge block; `_CustomReadFunc` then `pg_malloc(blkLen)` of arbitrary size up to ~2 GiB (int range). Memory pressure DoS. `[maybe — phase D]`
- **`_ArchiveEntry` stores `lclTocEntry` per TE.** No corruption surface in the write path (we're producing). [verified-by-code, pg_backup_custom.c:197-209]
- **`pg_compress_specification` byte → LZ4/zstd integration.** Compressor selection happens in `compress_io.c`'s `AllocateCompressor`; this file just hands off bytes. If LZ4/zstd library has a CVE, it transitively affects pg_restore. Out of scope here. `[fine]`

## Cross-references

- `WriteHead`/`ReadHead`/`WriteToc`/`ReadToc` — archiver.c:4170-4321.
- `ReadInt`/`WriteInt`/`ReadStr`/`WriteStr`/`ReadOffset`/`WriteOffset` — archiver.c:2076-2251.
- `AllocateCompressor`/`EndCompressor` — `compress_io.c`.
- `parallel_restore` — archiver.c:4828.

## Open questions

- The comment at line 461-469 ("Windows only runs on machines with strong store ordering") — true today for x86 Windows but not ARM64 Windows. Has anybody actually tested parallel custom-format restore on ARM64? `[unverified — phase D-adjacent]`
- `WriteOffset`/`ReadOffset` use a 1-byte flag plus N bytes for the offset. `offSize > sizeof(pgoff_t)` reads-and-discards bytes (archiver.c:2147-2149), pg_fatals only if those high bytes are nonzero. A hostile archive can set `offSize = 12` and stuff a large offset across the boundary; that's caught. [verified-by-code, archiver.c:2142-2151]

## Confidence tag tally
`[verified-by-code]=18 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=1 [maybe]=8 [fine]=2`
