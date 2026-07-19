---
path: src/port/pgmkdirp.c
anchor_sha: f25a07b2d94c
loc: 169
depth: deep
---

# src/port/pgmkdirp.c

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** re-pinned
> `4b0bf0788b0`→`f25a07b2d94c` (the doc for that exact commit, "Make
> pg_mkdir_p() tolerant of a concurrent directory creation"). LOC 148→169
> (+21). The commit **restructured the component walk** from "stat the
> prefix first, then mkdir" to "mkdir first, tolerate EEXIST when the path
> is already a directory" — concurrency-safe. The old stat-first
> "Component walk" description is now wrong; rewritten below, plus the new
> Windows-specific `GetFileAttributes` probe.

## Purpose

Provides `pg_mkdir_p(char *path, int omode)` — the engine behind `mkdir -p`:
create a directory and any missing parents, tolerating the case where the
target already exists. Adapted from FreeBSD's `mkdir(1)`. Used by `initdb`,
tablespace creation, and anywhere PG must materialize a directory tree.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_mkdir_p(char *path, int omode)` | `pgmkdirp.c:57` | 0 success; -1 (errno set) on failure. **Mutates `path`** to mark the failing level |

## Internal landmarks

- WIN32 prefix skip (`pgmkdirp.c:69-91`) — steps over `//network` and `C:`
  drive specifiers so they aren't treated as path components.
- **umask dance** (`:102-104`, `:118-119`, `:166`) — `oumask = umask(0)` then
  `numask = oumask & ~(S_IWUSR | S_IXUSR)` so intermediate parents get created
  with `u+wx` forced on (guaranteeing PG can descend); the original umask is
  restored just before the *final* component's `mkdir` (`:118-119`) so the leaf
  gets the caller's exact `omode`, and unconditionally restored at the end
  (`:166`). The header explains the POSIX equivalence to
  `mkdir -p -m $(umask -S),u+wx` (`:92-101`).
- **Component walk — mkdir-first, tolerate-EEXIST** (`:108-163`) — null-
  terminates `path` at each `/`, then `mkdir(path, last ? omode : S_IRWXU |
  S_IRWXG | S_IRWXO)` (`:121`). If `mkdir` fails it does NOT fail blindly:
  - **non-WIN32** (`:127-139`): if `errno == EEXIST` AND `stat(path)` says it's
    a directory, the level is tolerated and the walk continues; otherwise it
    restores `mkdir`'s errno and breaks with `retval = -1`.
  - **WIN32** (`:140-158`): `stat()` opens a handle and can transiently fail on
    a directory another process is concurrently creating, so the probe uses
    `GetFileAttributes(path)` (requests only `FILE_READ_ATTRIBUTES`, exempt from
    share-mode denial) and tolerates the level only if `errno == EEXIST` and the
    attribute reports `FILE_ATTRIBUTE_DIRECTORY`.
  This stat/mkdir ordering (mkdir first, check on failure) is what makes the
  routine safe against two backends racing to create the same tree.
  [verified-by-code, pgmkdirp.c:108-163]

## Invariants & gotchas

- **`path` is modified in place** and, on failure, left truncated at the
  directory level that failed — the header documents this (`:53-54`) so callers
  can report the exact failing prefix. Pass a writable copy, not a string
  literal.
- Assumes the path is already in **canonical form** (`/` separators); callers
  run `canonicalize_path` first (see `path.c`).
- Parents intentionally get permissive `0777`-minus-umask + forced `u+wx`; only
  the leaf honors `omode`. This is deliberate, not a bug — it mirrors GNU/BSD
  `mkdir -p`.
- `omode` is declared `int` (not `mode_t`) "to minimize dependencies for
  port.h" (`:49`).
- **Concurrent-creation tolerance (since `f25a07b2d94c`).** Two processes
  racing to create the same directory tree no longer make one of them fail:
  a level that `mkdir` reports `EEXIST` for is accepted as long as it really
  is a directory. On Windows the existence probe deliberately avoids `stat()`
  (which opens a handle and can transiently fail under share-mode denial while
  another process is mid-create) in favour of `GetFileAttributes()`
  (`:140-158`). [verified-by-code, pgmkdirp.c:121-158]

## Cross-refs

- `knowledge/files/src/port/pgcheckdir.c.md` — sibling directory primitive.
- `knowledge/files/src/port/path.c.md` — `canonicalize_path` run before this.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
