# `src/backend/storage/file/copydir.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~280
- **Source:** `source/src/backend/storage/file/copydir.c`

## Purpose

Cross-platform directory copy. Used primarily by `CREATE DATABASE …
STRATEGY FILE_COPY` and tablespace ops to replicate one data-directory
subtree into another. Replaces shelling out to `xcopy` on Windows.
Honors the `file_copy_method` GUC (COPY vs CLONE) so reflink-capable
filesystems can skip the bulk data transfer. [from-comment]
(`copydir.c:1-16`)

## Top of file

GUC `file_copy_method = FILE_COPY_METHOD_COPY` (line 35) — overridable
to `FILE_COPY_METHOD_CLONE` which uses platform-specific reflinks
(`copyfile()` on macOS, `FICLONE` ioctl on Linux).

## Public surface (copydir.h)

- `copydir(fromdir, todir, recurse)` — directory walk + per-file copy.
- `copy_file(fromfile, tofile)` — single regular-file copy with
  fsync of dest.

## Cross-refs

- Outbound: `fd.c` (`OpenTransientFile`, `FileSync` via underlying
  open), `common/file_utils.c` for clone.
- Inbound: `dbcommands.c` (CREATE DATABASE), `tablespace.c` (CREATE
  TABLESPACE), `reinit.c` (init-fork → main-fork copy for unlogged
  relations).

## Tag tally

`[from-comment]` 2 / `[verified-by-code]` 1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
