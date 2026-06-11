# `src/include/pgtar.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~89
- **Source:** `source/src/include/pgtar.h`

Tar archive format helpers — declarations for `src/port/tar.c`.
Used primarily by `pg_basebackup`, `pg_dump`, `pg_combinebackup`, and
the base-backup server-side code path (which emits a tar stream over
the replication protocol). [verified-by-code]

## API / declarations

- `TAR_BLOCK_SIZE = 512` (`pgtar.h:17`) — standard tar block.
- `enum tarError { TAR_OK=0, TAR_NAME_TOO_LONG, TAR_SYMLINK_TOO_LONG }`
  (`pgtar.h:19-24`) — returned by `tarCreateHeader`.
- `enum tarHeaderOffset` (`pgtar.h:37-56`) — byte offsets into a 512
  byte tar header:
  - `TAR_OFFSET_NAME = 0` (100 bytes string)
  - `TAR_OFFSET_MODE = 100` (8-byte tar number, excludes S_IFMT)
  - `TAR_OFFSET_UID = 108`, `TAR_OFFSET_GID = 116` (8-byte numbers)
  - `TAR_OFFSET_SIZE = 124` (8-byte number)
  - `TAR_OFFSET_MTIME = 136` (12-byte number)
  - `TAR_OFFSET_CHECKSUM = 148` (8-byte number)
  - `TAR_OFFSET_TYPEFLAG = 156` (1 byte; see TAR_FILETYPE_*)
  - `TAR_OFFSET_LINKNAME = 157` (100-byte string)
  - `TAR_OFFSET_MAGIC = 257` (`"ustar"` with terminating zero)
  - `TAR_OFFSET_VERSION = 263` (`"00"`)
  - `TAR_OFFSET_UNAME = 265`, `TAR_OFFSET_GNAME = 297`
    (32-byte strings)
  - `TAR_OFFSET_DEVMAJOR = 329`, `TAR_OFFSET_DEVMINOR = 337`
    (8-byte numbers)
  - `TAR_OFFSET_PREFIX = 345` (155-byte string)
  - Last 12 bytes of the block are unassigned.
- `enum tarFileType` (`pgtar.h:59-67`):
  - `TAR_FILETYPE_PLAIN = '0'`
  - `TAR_FILETYPE_PLAIN_OLD = '\0'` — backwards compat per POSIX
  - `TAR_FILETYPE_SYMLINK = '2'`
  - `TAR_FILETYPE_DIRECTORY = '5'`
  - `TAR_FILETYPE_PAX_EXTENDED = 'x'`
  - `TAR_FILETYPE_PAX_EXTENDED_GLOBAL = 'g'`

### Functions

- `tarCreateHeader(h, filename, linktarget, size, mode, uid, gid,
  mtime)` (`pgtar.h:69-72`) — fills a 512-byte header buffer.
- `read_tar_number(s, len)` / `print_tar_number(s, len, val)`
  (`pgtar.h:73-74`) — encode/decode the octal-or-base256 numeric
  fields used by tar headers.
- `tarChecksum(header)` (`pgtar.h:75`) — compute the checksum field.
- `isValidTarHeader(header)` (`pgtar.h:76`) — sanity check.
- `tarPaddingBytesRequired(len)` `static inline` (`pgtar.h:83-87`) —
  uses `TYPEALIGN(TAR_BLOCK_SIZE, len) - len`; works because
  TAR_BLOCK_SIZE is a power of 2.

## Notable invariants / details

- The "tar number" encoding supports both 11-digit octal (legacy
  POSIX) and base-256 (GNU extension) for sizes > 8 GB; the
  comment at `pgtar.h:29-30` notes the conversion functions handle
  both. [from-comment]
- String fields are filled and read with `strlcpy()` — so the
  trailing NUL is preserved within the field width but the field
  may not be NUL-terminated if the source exactly fills it.
  [from-comment]
- The checksum field is computed by summing all header bytes with
  the checksum field itself treated as 8 ASCII spaces. The
  `tarChecksum` function encapsulates this. [inferred]
- "Some fields are not used by PostgreSQL; see `tarCreateHeader()`"
  (`pgtar.h:35`) — `linkname` is only used for symlinks; `prefix`
  field is used to extend long names. PG doesn't use `pax_extended`
  headers when writing.
- `tarPaddingBytesRequired` relies on `TYPEALIGN` from c.h — so
  this header needs c.h to have been included first (transitively
  via postgres.h or postgres_fe.h).
- `TAR_FILETYPE_PLAIN_OLD = '\0'` is read but never written — old tar
  archives used `\0` to mean "plain file" before POSIX standardized
  `'0'`. [from-comment]

## Potential issues

- `pgtar.h:38-56` — the offset enum is hand-maintained against the
  POSIX ustar spec. Any new field would need to match the on-disk
  format exactly. No static-assert that `TAR_OFFSET_*` values match
  expected (e.g. `TAR_OFFSET_MAGIC == 257`). [ISSUE-style: no
  StaticAssert anchoring tarHeaderOffset values (nit)]
- `pgtar.h:69-72` — `tarCreateHeader` mixes tarError return with
  in-place buffer mutation; partial-failure leaves `h` modified.
  [ISSUE-api-shape: tarCreateHeader partial-failure mutation
  not flagged (nit)]
- `pgtar.h:75-76` — `isValidTarHeader` is a sanity check, not a
  cryptographic integrity check. Callers extracting from untrusted
  archives must do additional path validation (the `path_is_safe_for_extraction`
  in port.h is the companion).
  [ISSUE-security: isValidTarHeader does not validate against
  path traversal (likely)]
- `pgtar.h:76` — `isValidTarHeader(header)` only takes `const char *`,
  no length — assumes caller already has 512 bytes. Short read =
  buffer over-read. [ISSUE-correctness: isValidTarHeader has no
  length parameter (nit)]
- The header has no version field; if `pg_basebackup`'s tar format
  ever needed an extension, callers would have to grep the magic
  number area. [ISSUE-doc-drift: no provision for future
  PG-specific tar extensions (nit)]
