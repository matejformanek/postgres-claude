---
path: src/port/win32link.c
anchor_sha: e18b0cb7344
loc: 31
depth: read
---

# src/port/win32link.c

## Purpose

Windows replacement for the POSIX `link(2)` syscall — creates a hard
link from `src` to `dst`. Wraps Win32 `CreateHardLinkA`. Used by PG
in places that atomically install a file by hard-linking a temp file
into its final name (e.g. WAL segment recycling). `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int link(const char *src, const char *dst)` | `win32link.c:17` | Note POSIX argument order: `link(oldpath, newpath)` — `src` is the existing file |

## Internal landmarks

The whole body is 14 lines (`win32link.c:17-31`):
1. `CreateHardLinkA(dst, src, NULL)` — note the **argument order is
   reversed** from POSIX `link()`. CreateHardLink takes
   (`new_name`, `existing_name`), POSIX takes (`oldpath`, `newpath`).
   The wrapper swaps to present the POSIX-shape contract.
2. Zero return from `CreateHardLinkA` is failure (Win32 BOOL
   convention) — call `_dosmaperr(GetLastError())` and return -1.
3. Otherwise return 0.

## Invariants & gotchas

- **Filesystem support required.** Hard links only work on NTFS (and
  ReFS in some configurations); they fail on FAT32. Errors propagate
  via `_dosmaperr`.
- **`CreateHardLinkA` is ANSI-only** (no MBCS / Unicode path
  support). PG paths are ASCII or system-codepage; non-ASCII path
  components may fail on locales where the path doesn't round-trip
  through the system codepage.
- **Cross-volume link is rejected** — Win32 returns an error which
  maps to `EXDEV` via the `ERROR_NOT_SAME_DEVICE` entry in
  `win32error.c`.
- The trailing `NULL` to `CreateHardLinkA` is the security-attributes
  pointer (always NULL in PG — inherit default ACL).

## Cross-refs

- `knowledge/files/src/port/win32error.c.md` — `_dosmaperr` mapping
  for `ERROR_NOT_SAME_DEVICE`, `ERROR_FILE_NOT_FOUND` etc.
- `source/src/backend/access/transam/xlog.c` — WAL segment hard-link
  recycle path on Windows.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
