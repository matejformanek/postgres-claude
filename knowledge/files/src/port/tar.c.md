---
path: src/port/tar.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 235
depth: deep
---

# src/port/tar.c

## Purpose

Low-level tar **header** primitives shared by every PG component that reads or
writes tar streams: `pg_basebackup` / `pg_receivewal` (the `astreamer_tar`
pipeline), `pg_dump`'s tar archive format, and the server-side base-backup
sink. Handles the POSIX-ustar field encodings (octal and the GNU base-256
extension), the 512-byte header checksum, header validation, and header
construction. Constants like `TAR_OFFSET_*`, `TAR_BLOCK_SIZE`, and
`TAR_FILETYPE_*` live in `src/include/pgtar.h`. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void print_tar_number(char *s, int len, uint64 val)` | `tar.c:22` | Write a numeric field: octal+trailing-space, or GNU base-256 (`\200`-prefixed) if it doesn't fit |
| `uint64 read_tar_number(const char *s, int len)` | `tar.c:58` | Parse a numeric field (octal or base-256) |
| `int tarChecksum(const char *header)` | `tar.c:90` | Simple unsigned byte-sum, checksum field treated as 8 spaces |
| `bool isValidTarHeader(const char *header)` | `tar.c:112` | Verify checksum + magic/version (POSIX, GNU, pre-9.3 pg_dump) |
| `enum tarError tarCreateHeader(...)` | `tar.c:143` | Fill a 512-byte header for a file/dir/symlink |

## Internal landmarks

- `print_tar_number` (`tar.c:22-44`) — octal arm when `val < 1 << ((len-1)*3)`,
  else GNU base-256 with a leading `\200` byte. Comment notes only non-negative
  values are supported.
- `tarChecksum` (`:90-105`) — sums all 512 bytes treating the 8-byte checksum
  field at `TAR_OFFSET_CHECKSUM` as spaces, per POSIX.
- `isValidTarHeader` (`:112-134`) — checksum match plus one of three accepted
  magic strings, including the "not-quite-POSIX" form written by pre-9.3
  `pg_dump` (`:129-131`) for backward compat.
- `tarCreateHeader` (`:143-235`) — fills name, mode (masked `07777`, file-type
  bits stripped), uid/gid, size (zero for symlink/dir), mtime, typeflag, magic,
  hard-coded `postgres` uname/gname, then computes the checksum last.

## Invariants & gotchas

- **Name length is hard-capped at 99 bytes.** `tarCreateHeader` returns
  `TAR_NAME_TOO_LONG` / `TAR_SYMLINK_TOO_LONG` for anything longer (`tar.c:146-
  150`) — the ustar `name` and `linkname` fields are 100 bytes including the
  terminator. The 155-byte `prefix` field is left as nulls (`:229`), so PG does
  **not** use prefix-splitting to support long names.
- **Only symlinks to directories are supported**, signaled by a trailing slash
  on the name (`:156-168`); arbitrary symlink targets are not represented.
- The checksum **must** be written last (`:189`, `:232`) — it is computed over
  all other already-filled fields.
- uname/gname are hard-coded to `"postgres"` with two `XXX` comments asking
  whether the real owner should be recorded (`:215-221`) — long-standing and
  intentional for reproducibility; not flagged as an issue.

## Cross-refs

- `knowledge/files/src/fe_utils/astreamer_tar.c.md` — the streaming consumer
  (A11 backup-stream trust boundary).
- `knowledge/issues/pg_basebackup.md` — server-supplied tar field trust theme.
- `knowledge/files/src/port/strlcpy.c.md` — used to fill fixed-width fields.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
