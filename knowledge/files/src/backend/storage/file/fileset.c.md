# `src/backend/storage/file/fileset.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~185
- **Source:** `source/src/backend/storage/file/fileset.c`

## Purpose

Named temporary files in named directories. Where `OpenTemporaryFile`
(fd.c) gives you anonymous, auto-unlinked temp files, FileSet gives you
a *namespace* (a directory) so files can be looked up by name across
open/close cycles, and survive across transactions within the
creating backend. Layered under `SharedFileSet` (which adds DSM-based
shared ownership) and used directly by single-backend cases.
[from-comment] (`fileset.c:1-20`)

## Top of file

The set is *one or more directories* (one per temp tablespace
configured) — a per-set counter + creator PID disambiguates names.
Callers are responsible for explicit `FileSetDelete` /
`FileSetDeleteAll`. [from-comment] (`fileset.c:35-49`)

## Public surface (fileset.h)

- `FileSetInit(FileSet *)`
- `FileSetCreate(FileSet *, const char *name) → File`
- `FileSetOpen(FileSet *, const char *name, int mode) → File`
- `FileSetDelete(FileSet *, const char *name, bool error_on_failure)
  → bool`
- `FileSetDeleteAll(FileSet *)`

## Types

- `FileSet` (declared in fileset.h): `creator_pid`, `number` (counter
  in the creating backend), array of tablespace OIDs the set spans.

## Invariants

- File-to-tablespace mapping is by hash of the filename — same name
  always lands on the same tablespace within a FileSet
  (`ChooseTablespace`, line 34).
- Files are *not* auto-cleaned at backend exit; caller must Delete.

## Cross-refs

- Outbound: fd.c (PathNameCreateTemporaryFile / OpenTemporaryFile /
  CreateTemporaryDir), tablespace.c (GetTempTablespaces).
- Inbound: sharedfileset.c, buffile.c.

## Tag tally

`[from-comment]` 3 / `[verified-by-code]` 1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
