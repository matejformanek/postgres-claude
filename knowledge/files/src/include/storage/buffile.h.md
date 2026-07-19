# `src/include/storage/buffile.h`

- **Last verified commit:** `ef6a95c7c64`

## Purpose

Opaque `BufFile` typedef + API. See buffile.c for semantics.

## Surface

- Anonymous temp: `BufFileCreateTemp`, `BufFileClose`,
  `BufFileReadExact`, `BufFileReadMaybeEOF`, `BufFileWrite`,
  `BufFileSeek`, `BufFileTell`, `BufFileSeekBlock`, `BufFileSize`,
  `BufFileAppend`.
- Shared (FileSet): `BufFileCreateFileSet`, `BufFileExportFileSet`,
  `BufFileOpenFileSet`, `BufFileDeleteFileSet`,
  `BufFileTruncateFileSet`.

## Tag tally

`[verified-by-code]` 1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-buffer.md](../../../../subsystems/storage-buffer.md)
