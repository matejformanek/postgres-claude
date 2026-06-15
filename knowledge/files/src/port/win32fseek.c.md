---
path: src/port/win32fseek.c
anchor_sha: e18b0cb7344
loc: 75
depth: read
---

# src/port/win32fseek.c

## Purpose

Replacements for `fseeko()` / `ftello()` on MSVC builds — `_pgfseeko64`
and `_pgftello64`. Wraps MSVC's `_fseeki64`/`_ftelli64` (the 64-bit
offset variants) and adds explicit file-type discrimination, because
on Windows `fseek` against a pipe or character device does *not* fail
gracefully — it can return success while doing nothing, breaking
callers that assume seek-failure is detectable. `[from-comment]`
`[verified-by-code]`

The whole file is gated on `_MSC_VER` (`win32fseek.c:20`) — only
compiled for MSVC builds. MinGW uses different replacements.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int _pgfseeko64(FILE *stream, pgoff_t offset, int origin)` | `win32fseek.c:31` | Returns -1 with `errno` set when stream is not seekable |
| `pgoff_t _pgftello64(FILE *stream)` | `win32fseek.c:56` | Same gating logic as `_pgfseeko64` |

## Internal landmarks

Both functions follow identical structure:

1. Convert FILE* to Win32 HANDLE via `_get_osfhandle(_fileno(stream))`
   (`win32fseek.c:34`, `:59`).
2. Call `pgwin32_get_file_type(hFile)` to classify (`:36`, `:61`). On
   error (`errno != 0`), return -1 immediately.
3. Dispatch by type (`:40-47`, `:65-72`):
   - `FILE_TYPE_DISK` → delegate to real `_fseeki64`/`_ftelli64`.
   - `FILE_TYPE_CHAR` or `FILE_TYPE_PIPE` → `errno=ESPIPE`, return -1.
   - anything else → `errno=EINVAL`, return -1.

## Invariants & gotchas

- **Pipe/char `ESPIPE`** (`:43`, `:68`): POSIX-correct behavior — seek
  on a pipe is a hard error, not silent no-op. Without this wrapper,
  MSVC would let the seek "succeed" with undefined results.
- Returns `-1` on both `_pgfseeko64` paths (the type-mismatch and the
  type-error paths) — callers must check return value, not just
  `errno`, because `errno=0` after the dispatch is **never** a success
  for the non-disk branches.
- `pgoff_t` is the PG-portable 64-bit file offset typedef (mapping to
  `__int64` on MSVC, `off_t` elsewhere). The `_64` suffix in the function
  names reflects this.
- **Not compiled on MinGW.** MinGW's CRT has its own `fseeko`
  inheritance; the gating at `:20` excludes it. If a future MinGW
  build hits the same pipe-fseek bug, this file would need its gating
  loosened.

## Cross-refs

- `knowledge/files/src/port/win32common.c.md` — `pgwin32_get_file_type`
  is the type-classification helper used here.
- `source/src/include/port.h` — macro indirection routing `fseeko` /
  `ftello` to the `_pg*64` symbols on MSVC.
