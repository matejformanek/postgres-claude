---
path: src/port/pgcheckdir.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 92
depth: deep
---

# src/port/pgcheckdir.c

## Purpose

Provides `pg_check_dir(const char *dir)` — classifies a directory as
nonexistent / empty / dot-files-only / mount-point / non-empty. Used by
`initdb` to decide whether `PGDATA` is safe to initialize into, and by the
backend (e.g. tablespace creation) to refuse clobbering a populated directory.
The richer-than-boolean return lets callers emit precise diagnostics ("directory
exists but is not empty" vs "appears to be a mount point"). `[verified-by-code]`

## Public symbols

| Symbol | Site | Return code |
|---|---|---|
| `int pg_check_dir(const char *dir)` | `pgcheckdir.c:33` | 0 nonexistent · 1 empty · 2 only dot-files · 3 contains a mount point · 4 not empty · -1 access error (`errno` set) |

## Internal landmarks

- `opendir` + `ENOENT` mapping to 0 (`pgcheckdir.c:42-44`).
- `readdir` loop with the `errno = 0` idiom (`:46`) so a `NULL` return can be
  disambiguated between end-of-directory and error.
- `.`/`..` skipped (`:48-53`); other dot-files set `dot_found` (non-WIN32 only,
  `:54-59`); a `lost+found` entry sets `mount_found` (`:60-64`); any other entry
  immediately means "not empty" → result 4 and break (`:66-70`).
- Post-loop: `errno` check (`:73-74`), then a careful `closedir` that preserves
  the `readdir` errno on success (`:76-81`), then mount/dot reclassification
  (`:83-89`).

## Invariants & gotchas

- **The `errno = 0` before `readdir` is mandatory** — `readdir` returns `NULL`
  both at end-of-stream and on error, distinguishable only via `errno`. The
  code preserves the read errno across `closedir` so a successful close does not
  overwrite a real I/O error (`:77-81`).
- `lost+found` heuristic (result 3) is a Unix-filesystem convention used to warn
  that `PGDATA` was pointed at a mount root; it is suppressed on WIN32.
- Result 2 (only dot-files) lets `initdb` tolerate a directory holding only
  things like `.snapshot` without treating it as occupied.

## Cross-refs

- `knowledge/files/src/port/pgmkdirp.c.md` — sibling directory primitive.
- `knowledge/files/src/bin/initdb/initdb.c.md` — principal consumer.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
