# `src/backend/storage/file/sharedfileset.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~110
- **Source:** `source/src/backend/storage/file/sharedfileset.c`

## Purpose

`SharedFileSet` extends `FileSet` (fileset.c) with shared-ownership
reference counting via a DSM segment. Used by parallel query so that
multiple backends can read/write the same set of temp files (e.g.
parallel hash join spills) and the files survive until the *last*
participating backend detaches from the DSM. [from-comment]
(`sharedfileset.c:1-16`)

## Top of file

Two-line summary: "shared ownership semantics so that shared files
survive until the last user detaches". Uses spinlock + refcount in
shared memory, plus a DSM `on_dsm_detach` callback that decrements
the refcount and deletes the directory when it hits zero.

## Public surface (sharedfileset.h)

- `SharedFileSetInit(SharedFileSet *, dsm_segment *)`
- `SharedFileSetAttach(SharedFileSet *, dsm_segment *)`
- `SharedFileSetDeleteAll(SharedFileSet *)`

## Types

- `SharedFileSet` (declared in sharedfileset.h):
  spinlock + refcnt + embedded `FileSet fs` (the directory-set logic
  is delegated to fileset.c).

## Invariants

- Refcount starts at 1 on init; each `SharedFileSetAttach` bumps it;
  `SharedFileSetOnDetach` (DSM detach hook) decrements; the last
  detach calls `FileSetDeleteAll`.

## Cross-refs

- Outbound: `FileSetInit`, `FileSetDeleteAll` (fileset.c);
  `on_dsm_detach` (dsm.c); `SpinLock*`.
- Inbound: `nodeHash.c` (parallel hash), `parallel.c`.

## Tag tally

`[from-comment]` 3 / `[verified-by-code]` 1.
