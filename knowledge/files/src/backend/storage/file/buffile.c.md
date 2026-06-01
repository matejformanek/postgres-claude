# `src/backend/storage/file/buffile.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~960
- **Source:** `source/src/backend/storage/file/buffile.c`

## Purpose

"Buffered file" — a stdio-like layer atop fd.c VFDs, used for sort
runs, hash-join spill files, materialize node spills, and similar
backend-local temp data. Three things it adds on top of fd.c:
(1) a 1 × BLCKSZ ReadWrite buffer to amortize syscalls,
(2) transparent spanning across multiple physical files when a single
file would exceed `MAX_PHYSICAL_FILESIZE` (1 GB), and
(3) optional sharing across backends via FileSet / SharedFileSet.
[from-comment] (`buffile.c:12-43`)

## Top of file

Comment (lines 12–43) is the canonical "what BufFile is for" doc.
Key design choices stated there:
- BufFile structs are palloc'd → auto-freed on aborts.
- Underlying VFDs come from `OpenTemporaryFile` → auto-cleaned on
  abort too.
- 1 GB segment size, deliberately *not* RELSEG_SIZE, so large temp
  files distribute across multiple temp tablespaces.

## Public surface (buffile.h)

- Anonymous temp files: `BufFileCreateTemp`, `BufFileClose`.
- Read/write/seek: `BufFileReadExact`, `BufFileReadMaybeEOF`,
  `BufFileWrite`, `BufFileSeek`, `BufFileSeekBlock`, `BufFileTell`,
  `BufFileSize`, `BufFileAppend`.
- Shared (FileSet): `BufFileCreateFileSet`, `BufFileExportFileSet`,
  `BufFileOpenFileSet`, `BufFileDeleteFileSet`,
  `BufFileTruncateFileSet`.

## Types of note

- `BufFile` (lines 71–…): `numFiles` + dynamic `files[]` of File
  handles, `isInterXact`, `dirty`/`readOnly` flags, optional `fileset`
  + `name` for shared, `resowner`, current position
  (`curFile`,`curOffset`+`pos`), `nbytes` valid in buffer, then the
  BLCKSZ buffer itself.
- `BUFFILE_SEG_SIZE = MAX_PHYSICAL_FILESIZE / BLCKSZ = 131072` blocks.

## Invariants

- All files except the last have length exactly
  `MAX_PHYSICAL_FILESIZE` (1 GB). [from-comment] (`buffile.c:74`)
- The buffer is BLCKSZ-aligned in usage but BufFile reads/writes are
  byte-addressed; the buffer is filled/drained on block boundaries.
- Shared BufFiles (via FileSet) survive after the creating backend
  exits — that's the whole point. They are reclaimed when the
  containing DSM segment detaches (last attached backend).
- `BufFileCreateTemp` creates auto-deleting files; never use for data
  that must survive transaction abort.

## Cross-refs

- Outbound: `OpenTemporaryFile`, `FileReadV/WriteV/Seek` (fd.c);
  `FileSetCreate`/`Open`/`Delete` (fileset.c); for shared,
  `sharedfileset.c`.
- Inbound: `tuplesort.c`, `nodeHash.c`, `nodeHashjoin.c`,
  `tuplestore.c`, `parallel.c` (shared file passing).

## Open questions

- I didn't read the BufFileAppend / TruncateFileSet logic in detail;
  the segment-spanning semantics during truncate are `[unverified]`.

## Tag tally

`[from-comment]` 4 / `[verified-by-code]` 1 / `[unverified]` 1.
