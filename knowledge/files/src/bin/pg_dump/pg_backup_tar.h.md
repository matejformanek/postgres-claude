---
path: src/bin/pg_dump/pg_backup_tar.h
anchor_sha: 4b0bf0788b0
loc: 38
depth: read
---

# pg_backup_tar.h

- **Source path:** `source/src/bin/pg_dump/pg_backup_tar.h`
- **Lines:** 38
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_tar.c` (the tar-format archive driver — outside this doc's scope).

## Purpose

POSIX 1003.1 "ustar interchange format" tar header layout reference, plus a set of `LF_*` macro constants for the type-flag byte. **Pure documentation header** — defines nothing executable, only the 9 file-type macros. The exhaustive byte-offset/length/contents table at file top is the canonical reference for `pg_backup_tar.c`'s header reading and writing. [from-comment, pg_backup_tar.h:1-26]

## Header layout (per the file-top comment)

512-byte block. Field offsets and widths:

| Offset | Length | Contents |
|---|---|---|
| 0 | 100 | File name (NUL-terminated, max 99) |
| 100 | 8 | File mode (octal ASCII) |
| 108 | 8 | User ID (octal ASCII) |
| 116 | 8 | Group ID (octal ASCII) |
| 124 | 12 | File size (octal ASCII) |
| 136 | 12 | Modify time (Unix timestamp, octal ASCII) |
| 148 | 8 | Header checksum (octal ASCII) |
| 156 | 1 | Type flag (see `LF_*` below) |
| 157 | 100 | Linkname (NUL-terminated, max 99) |
| 257 | 6 | Magic `"ustar\0"` |
| 263 | 2 | Version `"00"` |
| 265 | 32 | User name (NUL-terminated, max 31) |
| 297 | 32 | Group name (NUL-terminated, max 31) |
| 329 | 8 | Major device ID (octal ASCII) |
| 337 | 8 | Minor device ID (octal ASCII) |
| 345 | 155 | File name prefix ("not used in our implementation") |
| 500 | 12 | Padding |
| 512 | s+p | File contents, padded to 512-byte boundary |

[from-comment, pg_backup_tar.h:4-26]

## Public surface

The `LF_*` typeflag macros [verified-by-code, pg_backup_tar.h:29-37]:

- `LF_OLDNORMAL '\0'` — normal disk file, Unix compatible
- `LF_NORMAL '0'` — normal disk file
- `LF_LINK '1'` — link to previously dumped file
- `LF_SYMLINK '2'` — symbolic link
- `LF_CHR '3'` — character special
- `LF_BLK '4'` — block special
- `LF_DIR '5'` — directory
- `LF_FIFO '6'` — FIFO special
- `LF_CONTIG '7'` — contiguous file

## Invariants & gotchas

- **File-size field is 12 octal-ASCII bytes** — fits values up to `0o777777777777` = 8 GB minus 1. **Files larger than 8 GiB cannot be represented in standard ustar.** GNU tar and POSIX.1-2001 ("pax") have extensions, but plain ustar (and the comment says "ustar interchange format") tops out here. pg_backup_tar.c must handle this — large data members in a pg_dump tar archive would silently overflow this field. **See ISSUE-pg-dump-A3-pg_backup_tar-8gb-size-limit.** [from-comment + standards, pg_backup_tar.h:11] [maybe]
- **Filename field is 100 bytes** (99 chars + NUL). pg_dump TOC entries use names like `<tablename>.dat`; long table names (PostgreSQL allows 63 chars) plus suffix could approach the limit but generally fit. The 155-byte "prefix" field is **explicitly not used** ("not used in our implementation"), so the effective filename limit is 99 chars in pg_dump's tar archives. [from-comment, pg_backup_tar.h:7, 22]
- **All numeric fields are octal ASCII.** Not binary. Parsing this is `strtol(.., 8)` in `pg_backup_tar.c`. [from-comment, pg_backup_tar.h:8-13]
- **Type flag is a single byte.** `LF_OLDNORMAL` (`'\0'`) handles legacy tars predating the `'0'` convention. pg_dump itself writes `LF_NORMAL` (`'0'`) for data files. [verified-by-code, pg_backup_tar.h:29-30]
- **Header checksum at offset 148 is 8 bytes** but conventionally only 7 useful (6 octal digits + NUL + space). Parsed by `pg_backup_tar.c`. [from-comment, pg_backup_tar.h:13]
- **No `LF_GNUTYPELONGNAME`, `LF_GNUTYPELONGLINK`, etc.** — pg_dump's tar format does not support GNU long-name extensions. Limits filename length to 99. [verified-by-code, pg_backup_tar.h:29-37 vs GNU tar headers]

## Phase D — hostile-archive surface

- **Filename buffer overflow defense relies on the reader.** A hostile tar archive could leave the 100-byte filename field unterminated. `pg_backup_tar.c` must clamp / re-terminate. (Not covered here; that's a `pg_backup_tar.c` concern.) [inferred]
- **Octal-ASCII parsing.** Any field containing non-octal bytes would yield short reads via `strtol`; well-defined per C standard. No injection surface.
- **Type-flag values outside `LF_*`** — the file lists 9 specific bytes; `pg_backup_tar.c` must decide what to do with e.g. `LF_GLOBAL_HEADER ('g')` or `LF_XHDR ('x')` (pax extensions). Standard guidance: skip unknown. [inferred]
- **8 GiB size cap** as above — silent truncation on write would mismatch actual file size on read, leading to mis-parsing of subsequent headers. [maybe]

## Cross-references

- `pg_backup_tar.c` — the actual reader/writer that consumes this header layout.
- POSIX 1003.1 "ustar interchange format" — the external standard this header documents.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=8 [inferred]=2 [maybe]=2`
