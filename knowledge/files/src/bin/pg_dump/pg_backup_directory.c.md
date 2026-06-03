---
path: src/bin/pg_dump/pg_backup_directory.c
anchor_sha: 4b0bf0788b0
loc: 820
depth: deep
---

# pg_backup_directory.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_directory.c`
- **Lines:** 820
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_archiver.h`, `pg_backup_archiver.c` (`WriteHead/ReadHead/WriteToc/ReadToc/parallel_restore`), `compress_io.c`/`compress_io.h` (`InitCompressFileHandle`, `InitDiscoverCompressFileHandle`, `CompressFileHandle`), `parallel.c` (`ParallelBackupStart/End`).

## Purpose

Implements the **directory format (`-Fd`)** — a directory containing a `toc.dat` file + one compressed file per dumpable data entry (named `<dumpId>.dat[.gz/.lz4/.zst]`) + per-LO files `blob_<oid>.dat[.gz/...]` + one `blobs_<dumpId>.toc` file per BLOBS group mapping OID → filename. The TOC file is uncompressed by pg_dump but can be accepted compressed if the user gzipped it. [from-comment, pg_backup_directory.c:5-20]

This format **supports both parallel dump and parallel restore** (only one that supports parallel dump besides the tar appending; custom supports only parallel restore). It is also a primary Phase D surface for **path traversal via attacker-controlled filenames in the archive**.

## On-disk layout

```
<dir>/
├── toc.dat              header + TOC, format byte = archTar (sic), per-TE WriteStr(filename)
├── <dumpId>.dat[.gz]    one per TABLE DATA / data-bearing entry
├── blob_<oid>.dat[.gz]  one per large object
└── blobs_<dumpId>.toc   per-BLOBS-group LO catalog (or "blobs.toc" pre-v16)
```

[verified-by-code, pg_backup_directory.c:5-9; 110-190; 549-573]

## Public surface

Only `InitArchiveFmt_Directory(ArchiveHandle *AH)` (109). Populates the function-pointer slots; opens `toc.dat` in either mode; in read mode parses head+TOC under `format = archTar` then restores `format = archDirectory` (lines 180-182 — the directory format **deliberately writes/reads its TOC as if it were tar** so the two formats are inter-extractable). [verified-by-code, pg_backup_directory.c:177-183; 553-561]

## Key data structures

- `lclContext` (48-59) — per-archive state:
  - `char *directory` — backup root (the user's argument to `-f`).
  - `CompressFileHandle *dataFH` — currently open data file.
  - `CompressFileHandle *LOsTocFH` — currently open `blobs_NNN.toc` file.
  - `ParallelState *pstate` — leader-only.
- `lclTocEntry` (61-64) — per-TE: just `char *filename` (basename, not absolute).

## Key functions

### Write path

- `InitArchiveFmt_Directory` write branch (158-162) — calls `create_or_open_dir(ctx->directory)` (from `file_utils.c`) which accepts an empty existing dir or creates a new one. [verified-by-code, pg_backup_directory.c:158-162]
- `_ArchiveEntry` (197-218) — assigns filename: `blobs_<dumpId>.toc` for BLOBS, `<dumpId>.dat` for TABLE DATA, NULL otherwise.
- `_StartData` (289-302) — `setFilePath` builds `<dir>/<filename>`, `InitCompressFileHandle(AH->compression_spec)` creates the per-file compressor, `open_write_func(fname, "wb", ...)` opens.
- `_WriteData` (313-322) — delegates to `CFH->write_func`.
- `_EndData` (330-340) — `EndCompressFileHandle` closes and pg_fatals on close failure.
- `_StartLOs` (602-617) — opens `blobs_<dumpId>.toc` (uncompressed) in append mode (`"ab"`).
- `_StartLO` (624-635) — builds `<dir>/blob_<oid>.dat`, opens with the archive's compression spec.
- `_EndLO` (642-658) — closes the blob file, then writes `"<oid> blob_<oid>.dat\n"` to the LO TOC.
- `_EndLOs` (665-673) — closes the LO TOC.
- `_CloseArchive` (530-576) — forks parallel workers (`ParallelBackupStart`), opens `toc.dat` (uncompressed), writes head+TOC, calls `WriteDataChunks`, ends workers, and recursively fsyncs the directory if `dosync`. [verified-by-code, pg_backup_directory.c:530-576]

### Read path

- `InitArchiveFmt_Directory` read branch (164-189) — open `toc.dat` via `InitDiscoverCompressFileHandle` (the "discover" variant tries `.gz/.lz4/.zst` extensions). Read head and TOC.
- `_ReadExtraToc` (249-265) — `ReadStr(filename)`; if empty, NULL out.
- `_PrintTocData` (377-393) — if BLOBS, `_LoadLOs`; else `_PrintFileData(<dir>/<filename>)`.
- `_PrintFileData` (346-371) — open file via `InitDiscoverCompressFileHandle` (auto-decompress), loop `CFH->read_func` → `ahwrite()` until EOF. [verified-by-code, pg_backup_directory.c:346-371]
- `_LoadLOs` (396-452) — open `blobs.toc` (pre-v16) or `blobs_<dumpId>.toc` (≥ v16) and parse each line via `sscanf(line, "%u %" CppAsString2(MAXPGPATH) "s\n", &oid, lofname)`. Then `snprintf(path, MAXPGPATH, "%s/%s", ctx->directory, lofname)` and `_PrintFileData(path)`. [verified-by-code, pg_backup_directory.c:396-452]

### Parallel

- `_PrepParallelRestore` (707-762) — for each data-bearing TE, `stat(<dir>/<filename>)` and put `st_size` into `te->dataLength`. If compression is on and the plain filename doesn't exist, retry with `.gz`/`.lz4`/`.zst`. For BLOBS, the toc file's size is a poor proxy, so multiply by **1024 arbitrarily** (line 757-760). [verified-by-code, pg_backup_directory.c:707-762]
- `_Clone` (767-785) — flat-copy lclContext; intentionally does NOT clone pstate (leader-only). [verified-by-code, pg_backup_directory.c:767-785]
- `_WorkerJobRestoreDirectory` (816-820) → `parallel_restore`.
- `_WorkerJobDumpDirectory` (799-810) → `WriteDataChunksForTocEntry`.

### `setFilePath` (681-695)

```c
strcpy(buf, dname);
strcat(buf, "/");
strcat(buf, relativeFilename);
```

Pre-checks `strlen(dname) + 1 + strlen(relativeFilename) + 1 > MAXPGPATH` → pg_fatal. **No further path-component validation** on `relativeFilename`. [verified-by-code, pg_backup_directory.c:681-695]

## Phase D notes [attacker-controlled-archive path traversal]

This is the **second-highest Phase D surface** in the backend group. A hostile `toc.dat` controls the per-TE `filename` field and the per-LO line in `blobs_*.toc`. The only sanity check is `_LoadLOs`'s `sscanf` width-limit `%" CppAsString2(MAXPGPATH) "s` (line 432).

- **Path traversal via `te->filename`.** `_ReadExtraToc` stores the string verbatim. `setFilePath` concatenates `<dir>/<filename>` into a buffer. If a hostile archive writes `filename = "../../etc/shadow"` then `_PrintFileData` will try to **read** that file and `ahwrite` its contents into the restore script. Read-side traversal → information disclosure. `[maybe — phase D]` [verified-by-code, pg_backup_directory.c:259-263; 388-392; 681-695]
- **Write-side traversal during dump? Not directly.** `_ArchiveEntry` (203-217) constructs filename as `blobs_<dumpId>.toc` or `<dumpId>.dat` — both purely numeric and bounded by dumpId range. Safe in the dumping flow. `[fine]`
- **`_LoadLOs` parses LO TOC lines:** `sscanf(line, "%u %" CppAsString2(MAXPGPATH) "s\n", &oid, lofname)`. The `%MAXPGPATH s` (note: width spec is MAXPGPATH, which is the **size of the lofname buffer** declared as `char lofname[MAXPGPATH + 1]`). The format-string width does **not** include the NUL terminator slot, so this is correct (sscanf writes up to MAXPGPATH chars + NUL). [verified-by-code, pg_backup_directory.c:428-434] But `lofname` itself can be `../../foo` → `snprintf(path, MAXPGPATH, "%s/%s", ctx->directory, lofname)` then `_PrintFileData(path)` reads that file. Same traversal class as above. `[maybe — phase D]`
- **Symlink following.** Neither `fopen` (via `InitDiscoverCompressFileHandle`) nor `stat` use `O_NOFOLLOW`. If `<dir>/<filename>` is a symlink to /etc/passwd, dumping (write-side, where the file is the dumper's own creation in a brand-new or empty dir) wouldn't follow because we open `PG_BINARY_W`. Restore-side reads do follow. `[maybe — phase D]`
- **`create_or_open_dir` accepts an existing non-empty dir** (line 159 comment "we accept an empty existing directory" but the implementation in `file_utils.c` actually only fails if the dir contains entries — verify there). Restore mounted onto a dir with pre-existing files would have those files read if their names match `<dumpId>.dat`. `[unverified — phase D]`
- **`_PrintFileData` allocates `DEFAULT_IO_BUFFER_SIZE`** (typically 8 KiB; check `file_utils.h`); no integer-overflow risk on the read side. [verified-by-code, pg_backup_directory.c:360-368] `[fine]`
- **`blobs_NNN.toc` line parsing** (432) trusts `sscanf` for the OID; if line is malformed, pg_fatal. No injection via malformed line. `[fine]`
- **`MAXPGPATH` truncation in `_StartLO`** (630): `snprintf(fname, MAXPGPATH, "%s/blob_%u.dat", ctx->directory, oid)`. If `ctx->directory` is near MAXPGPATH, the filename is silently truncated; subsequent `open_write_func` may either create a wrong file or fail. **Not checked**. `[maybe — phase D]`
- **The `dosync → sync_dir_recurse` call** (572-573) iterates the directory; if a hostile archive somehow placed extra files there, those get fsynced too. Not a security hole, but a fingerprinting surface. `[fine]`
- **Format-byte confusion.** `_CloseArchive` writes `AH->format = archTar` then `WriteHead`, then restores `archDirectory`. The TOC inside `toc.dat` therefore claims `format = archTar`. On read, `_discoverArchiveFormat` sees the dir, dispatches to `InitArchiveFmt_Directory`, which sets `format = archTar` before `ReadHead`, then back. Cross-check at archiver.c:4248 is satisfied. Works but is fragile to anyone reading toc.dat with a hex editor. [from-comment, pg_backup_directory.c:553-558] `[fine]`

## Cross-references

- `InitDiscoverCompressFileHandle`, `InitCompressFileHandle`, `EndCompressFileHandle` — `compress_io.c`.
- `create_or_open_dir`, `sync_dir_recurse` — `common/file_utils.c`.
- `ParallelBackupStart`, `ParallelBackupEnd`, `WriteDataChunksForTocEntry` — `parallel.c`, `archiver.c:2599`.
- `parallel_restore` — `archiver.c:4828`.

## Open questions

- Does `create_or_open_dir` actually reject a non-empty directory, or does it merely create or reuse it? The comment ("we accept an empty existing directory") implies the former, but the function lives in `common/file_utils.c` and should be verified. `[unverified — phase D]`
- Was a deliberate decision made to allow read-side path traversal via filename, or is it considered an unsupported threat model? The directory format archive is conceptually like a tarball you'd extract — if you trust the source enough to restore as superuser, presumably you trust the filenames. But there's no explicit rejection of `..` in filenames anywhere. `[unverified — phase D]`

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=3 [maybe]=5 [fine]=4`
