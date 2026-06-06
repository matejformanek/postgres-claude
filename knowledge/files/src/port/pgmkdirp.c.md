---
path: src/port/pgmkdirp.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 148
depth: deep
---

# src/port/pgmkdirp.c

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
- **umask dance** (`:103-105`, `:119-120`, `:144-145`) — temporarily sets umask
  so intermediate parents get created with `u+wx` forced on (guaranteeing PG can
  descend), while the *final* component gets the caller's exact `omode`. Restores
  the original umask at the end. The header explains the POSIX equivalence to
  `mkdir -p -m $(umask -S),u+wx` (`:93-101`).
- Component walk (`:109-142`) — null-terminates at each `/`, `stat`s the prefix;
  if it exists and is a directory, continue; if it exists and is *not* a
  directory, fail `EEXIST`/`ENOTDIR`; else `mkdir` it (final component with
  `omode`, parents with `0777`).

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

## Cross-refs

- `knowledge/files/src/port/pgcheckdir.c.md` — sibling directory primitive.
- `knowledge/files/src/port/path.c.md` — `canonicalize_path` run before this.
