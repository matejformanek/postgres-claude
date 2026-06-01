# `src/include/storage/sharedfileset.h`

- **Last verified commit:** `ef6a95c7c64`

## Surface

- `SharedFileSet` struct: spinlock + refcnt + embedded `FileSet`.
- `SharedFileSetInit`, `SharedFileSetAttach`, `SharedFileSetDeleteAll`.

## Tag tally

`[verified-by-code]` 1.
