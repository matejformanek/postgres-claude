---
path: src/bin/pg_dump/pg_backup_tar.c
anchor_sha: f25a07b2d94c
loc: 1197
depth: deep
---

# pg_backup_tar.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_tar.c`
- **Lines:** 1197
- **Last verified commit:** `f25a07b2d94c`

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** re-pinned
> `4b0bf0788b0`→`f25a07b2d94c`. The `7ca548f23a60` pg_dumpall revert left
> the tar format module untouched (LOC 1197). Verified cites:
> InitArchiveFmt_Tar 120, _CloseArchive 768, _tarAddFile 988, compression
> fatal 194. AUDIT clean.
- **Companion files:** `pg_backup_archiver.h` (`READ_ERROR_EXIT`, `WRITE_ERROR_EXIT`), `pg_backup_archiver.c` (`WriteHead`, `WriteToc`, `WriteDataChunks`, `RestoreArchive`), `pg_backup_tar.h` (just the `InitArchiveFmt_Tar` extern), `pgtar.c`/`pgtar.h` (`tarCreateHeader`, `tarChecksum`, `read_tar_number`, `tarPaddingBytesRequired`, `TAR_BLOCK_SIZE`, `TAR_OFFSET_NAME`, `TAR_OFFSET_SIZE`, `TAR_OFFSET_CHECKSUM`, `isValidTarHeader`).

## Purpose

Implements the **tar format (`-Ft`)** — a single uncompressed tar file containing the same per-member layout as the directory format (`toc.dat`, `<dumpId>.dat`, `blobs_<dumpId>.toc`, `blob_<oid>.dat`), plus a `restore.sql` script appended at the end for humans. The two formats are intentionally interchangeable: if you `tar -x` a tar dump you get a directory dump. [from-comment, pg_backup_tar.c:5-13]

**No compression supported** (line 193-194: `pg_fatal("compression is not supported by tar archive format")`). The comment explains: `gzdopen` is buffered and breaks file positioning. [from-comment, pg_backup_tar.c:189-194]

**No parallel dump or restore** (`AH->WorkerJobDumpPtr = NULL; AH->WorkerJobRestorePtr = NULL;` at line 148-149; `AH->ClonePtr = NULL`). Reading also requires entries to appear in order; out-of-order restore is rejected (line 1089-1093).

This is a **major Phase D surface** — tar parsers are notoriously fragile (path traversal via `../`, symlinks, special headers, size overflow). pg_dump's parser is a hand-rolled subset that doesn't handle PAX, GNU long-name, or symlink entries; those manifest as either pg_fatal or as unexpected `filename` strings.

## On-disk layout

```
tar header (TAR_BLOCK_SIZE = 512 bytes)
  ├ name[100]   filename
  ├ ...
  ├ size[12]    octal size
  ├ checksum[8] octal sum-of-bytes
  └ ...
data padded to 512-byte multiple
... repeat per member ...
2 × 512 NULs (EOF marker)
```

Each member is: header → data → padding. The first member written is `toc.dat` (head+TOC); then the data files; then `restore.sql`. [verified-by-code, pg_backup_tar.c:769-851; 1186-1197]

## Public surface

Only `InitArchiveFmt_Tar(ArchiveHandle *AH)` (120). Populates pointers, opens `tarFH` (stdin/stdout or file), `checkSeek`, pg_fatals on compression-set, and in read-mode opens member `toc.dat` and calls `ReadHead`+`ReadToc`. [verified-by-code, pg_backup_tar.c:120-227]

## Key data structures

- `TAR_MEMBER` (66-76):
  - `nFH` — file handle being read/written for this member's data (in write mode, points at `tmpFH`).
  - `tarFH` — the underlying tar file (shared).
  - `tmpFH` — per-member temp file (write mode only).
  - `targetFile` — the in-archive filename.
  - `mode` — 'r' or 'w'.
  - `pos`, `fileLen` — read-time bookkeeping.
- `lclContext` (78-89):
  - `hasSeek`, `filePos` — for TOC-area positioning.
  - `loToc` — `TAR_MEMBER *` for the open `blobs_NNN.toc` while writing LOs.
  - `tarFH` — main tar file.
  - `tarFHpos`, `tarNextMember` — read-time positions.
  - `FH` — current member.
  - `isSpecialScript`, `scriptTH` — used while emitting `restore.sql`.
- `lclTocEntry` (91-95): `TH` (member), `filename`.

## Write path

- `tarOpen` (301-395) — write-mode branch creates a `TAR_MEMBER` and opens a **temp file** (`tmpfile()` on Unix; `_tempnam` + `O_RDWR|O_CREAT|O_EXCL|O_TEMPORARY` loop on Windows). **Sets umask to deny group/other access first** (line 344) — protecting confidentiality against post-crash tmpfile recovery. [from-comment, pg_backup_tar.c:338-345]
- `_WriteData` (540-546) → `tarWrite(data, dLen, tctx->TH)` → `fwrite(buf, len, nFH)` (the per-member temp file).
- `_EndData` (548-556) → `tarClose` → `_tarAddFile`.
- `_tarAddFile` (988-1037) — Determine `fileLen = ftello(tmp)`; `_tarWriteHeader` (composing 512-byte header via `tarCreateHeader`); copy from temp file into the tar file in 32 KiB chunks via `fread`+`fwrite`; pad to TAR_BLOCK_SIZE multiple; `fclose(tmp)` deletes the tmpfile. **Sanity check `len != fileLen` → pg_fatal.** [verified-by-code, pg_backup_tar.c:988-1037]
- `_tarWriteHeader` (1186-1197) — `tarCreateHeader(h, targetFile, NULL, fileLen, 0600, 04000, 02000, time(NULL))`. Mode `0600`, uid/gid placeholders. [verified-by-code, pg_backup_tar.c:1186-1197]
- `_CloseArchive` (768-854) — write head+TOC into `toc.dat`, then all data, then **build restore.sql by running RestoreArchive in a special mode** (`ctx->isSpecialScript = 1; ctx->scriptTH = th; CustomOutPtr = _scriptOut`). The recursive restore writes into the tar instead of the DB. Finally appends 2 × 512 NUL bytes (the standard tar EOF marker) and fsyncs if requested. [verified-by-code, pg_backup_tar.c:768-854]

## Read path [Phase D primary surface]

- `tarOpen` (301-331) — read-mode branch calls `_tarPositionTo(filename)`. If filename != NULL and not found, **pg_fatal**. If NULL (scanning for any), returns NULL on EOF.
- `_tarPositionTo` (1040-1111) — Walks the tar from `tarFHpos` to `tarNextMember`; reads a header via `_tarGetHeader`; if the header's name doesn't match the wanted file, checks **whether the requested-later file's data is needed by an earlier TOC entry** (line 1088-1093):
  ```
  id = atoi(th->targetFile);
  if ((TocIDRequired(AH, id) & REQ_DATA) != 0)
      pg_fatal("restoring data out of order is not supported …");
  ```
  Otherwise skips this member's data (blks = padded_len / 512) and reads the next header. [verified-by-code, pg_backup_tar.c:1040-1111]
- `_tarGetHeader` (1113-1183) — Reads one 512-byte block. **Computes checksum and compares to the header's octal-encoded checksum field** via `tarChecksum(h)` and `read_tar_number(&h[TAR_OFFSET_CHECKSUM], 8)`. On mismatch and the block is all-NULs, silently skips (tar uses NUL blocks as padding/EOF). On mismatch with non-NUL, **continues looping** until a valid block is found — but then later pg_fatals with `"corrupt tar header found …"` (line 1175-1177). Wait — re-reading: the loop break sets `gotBlock = true` regardless, then **after the loop** it pg_fatals if `chk != sum`. So the loop's "continue if non-NUL" is dead code; non-NUL with wrong checksum eventually reaches pg_fatal. [verified-by-code, pg_backup_tar.c:1126-1182]
- Name is read as 100 bytes via `strlcpy(tag, &h[TAR_OFFSET_NAME], 100 + 1)` — bounded to 100 chars. [verified-by-code, pg_backup_tar.c:1167-1168]
- `fileLen = read_tar_number(&h[TAR_OFFSET_SIZE], 12)` — `pgoff_t`, parsed from 12-byte octal field. `read_tar_number` (in `pgtar.c`) is supposed to bounds-check, but worth verifying separately. [verified-by-code, pg_backup_tar.c:1170]
- `tarRead` (510-526) — clamps `len` to `min(len, fileLen - pos)`. Prevents over-read of one member into the next. [verified-by-code, pg_backup_tar.c:510-526]
- `_LoadLOs` (642-714) — version ≥ 1.16: read the BLOBS TOC entry's `te->tag` as an OID (via `atooid`), build `"blob_<oid>.dat"`, scan forward via `tarOpen`. Otherwise: just scan forward until finding the first `blob_*` member.
  - For each member starting with `"blob_"`: `oid = atooid(&th->targetFile[5])`; `tarOpen` → read its data via `tarRead` 4 KiB at a time → `ahwrite`.
  - **The comment at 698-706 admits "This coding would eat all the rest of the archive if there are no LOs ... but this function shouldn't be called at all in that case."** That's a robustness assumption — if a BLOBS TOC entry exists with zero blobs in the tar, the loop reads to EOF. Not a security issue but a denial of trust hint. [from-comment, pg_backup_tar.c:701-707]

## Phase D notes [tar parser hazards]

- **Path traversal via `name[100]`.** `strlcpy(tag, &h[TAR_OFFSET_NAME], 101)` — bounded. Then `th->targetFile = pg_strdup(tag)`. The string can contain `../../etc/shadow`. The directory format passes filenames to `setFilePath` which concatenates blindly. **In tar, however, no filename is ever joined with a base directory**: the tar member is found by linear search and read in-place from the tar file. Path traversal would have to manifest as `_LoadLOs` doing `tarOpen(blob_<oid>.dat)` with an attacker-controlled OID encoded as path — but the format string is `"blob_%u.dat"` (line 668) → only digits. **Read-side traversal is NOT exploitable via tar format alone.** `[fine]`
- **Symlink handling.** The hand-rolled tar parser only handles regular file headers; the typeflag byte is at offset 156 (not in TAR_OFFSET_* set listed). Looking at the code, **typeflag is never checked** — a symlink, hardlink, or special-device entry is treated as a regular file with whatever name and size. The data is read but never followed (no `open` of `targetFile` by absolute path). So symlink entries don't cause filesystem traversal; they're just treated as members with the symlink target appended in data. `[fine]`
- **Integer overflow on `fileLen`.** `read_tar_number(&h[TAR_OFFSET_SIZE], 12)` parses 12 octal chars → max `0o777777777777` ≈ 2^36 ≈ 64 GiB. Stored in `pgoff_t` (signed 64-bit). `_tarPositionTo` then computes `len = fileLen + tarPaddingBytesRequired(fileLen); blks = len / 512;` for the skip loop (1095-1100). A hostile size of `0o7777_7777_7777` causes `len ≈ 2^36`, `blks ≈ 2^27` → 128 million 512-byte `_tarReadRaw` calls — DoS but bounded by actual file size since fread returns short. `[maybe — phase D]`
- **GNU/PAX extensions ignored.** `_tarGetHeader` doesn't handle GNU long-name (`L` typeflag) or PAX (`x`/`g`) headers. They'd be treated as regular members with garbage names. If pg_dump ever needs filenames > 100 chars, this format silently truncates — `_StartLO` writes `blob_%u.dat` (a few bytes) and `_ArchiveEntry` writes `%d.dat` (also small), so in practice not a problem. `[fine]`
- **Checksum-mismatch loop.** Lines 1150-1164: if checksum fails AND block is all NULs, continue. The for-loop sets `gotBlock = true` if any byte is non-zero, then the outer `while` exits. The subsequent `if (chk != sum) pg_fatal(...)` catches the non-NUL-but-corrupt case. Net effect: NUL padding is skipped, corrupt non-NUL is fatal. Correct. [verified-by-code, pg_backup_tar.c:1126-1177] `[fine]`
- **`isValidTarHeader(AH->lookahead)`** (archiver.c:2375) is checked when discovering format; a non-tar file claiming to be tar via filename extension still gets rejected here. `[fine]`
- **Out-of-order restore detection.** `_tarPositionTo` pg_fatals if the user requests data from a file that comes BEFORE the current tar position AND that file's TOC entry has `REQ_DATA`. This is a sequential-streaming constraint, not security. [verified-by-code, pg_backup_tar.c:1088-1093] `[fine]`
- **`_CloseArchive` recursive restore for restore.sql.** Lines 814-829 copy `ropt`, set `ropt->filename = NULL; ropt->dropSchema = 1;`, then `RestoreArchive((Archive *) AH, false)`. The `CustomOutPtr = _scriptOut` reroute means all the SQL gets captured into a tar member instead of stdout. This is correct, but **it runs the entire RestoreArchive plumbing twice on dump-time** — once virtually to build restore.sql, once for real... actually no, in dump mode the second isn't done. But the trick is that `RestoreArchive` is called during a DUMP. Surprising but contained. [verified-by-code, pg_backup_tar.c:814-829] `[fine]`
- **`atooid(&th->targetFile[5])`** — buffer offset trusts `targetFile` is at least 5 chars; checked indirectly by `strncmp(th->targetFile, "blob_", 5) == 0` on line 678. `[fine]`
- **`uid/gid = 04000/02000` (octal) hardcoded** in `_tarWriteHeader` (line 1192). These are nonsensical default values — actually 04000 = 2048 and 02000 = 1024 in decimal, but tar treats them as numeric uid/gid. `0600` is the mode. **The point**: extracted files don't preserve the dumper's identity, which is correct (a tar dump is restored as the restorer's identity). `[fine]`
- **Tmpfile umask** (line 344): explicit `umask(S_IRWXG | S_IRWXO)` before `tmpfile()` — defense against tmpfile retention exposing data, per the comment. **Good practice.** [from-comment, pg_backup_tar.c:338-345] `[fine]`

## Cross-references

- `tarCreateHeader`, `tarChecksum`, `read_tar_number`, `tarPaddingBytesRequired`, `isValidTarHeader`, `TAR_BLOCK_SIZE`, `TAR_OFFSET_*` — `pgtar.c`/`pgtar.h`. (These are the high-value Phase D files; `read_tar_number` correctness gates this format's safety.)
- `_tarPositionTo` callers: `tarOpen('r' mode)`.
- `_scriptOut`, `_LoadLOs`, `_StartLO/EndLO` — all use the special script-output detour.

## Open questions

- Does `read_tar_number` in `pgtar.c` reject negative values / non-octal bytes correctly? Needs separate audit. `[unverified — phase D]`
- The 100-char filename truncation by `strlcpy` in `_tarGetHeader` — if a real-world archive ever has a member named ≥ 100 chars (it shouldn't with pg_dump's emitted names), the truncated name would mis-match the requested name and trigger the "could not find file" pg_fatal. Not a corruption hazard. `[fine]`
- Why is the umask trick applied to tmpfile but not to the main tarFH (`fopen(fSpec, "wb")`)? The main tar is the user's chosen output file; we trust their umask. `[inferred]`

## Confidence tag tally
`[verified-by-code]=18 [from-comment]=4 [from-readme]=0 [inferred]=1 [unverified]=1 [maybe]=1 [fine]=9`
