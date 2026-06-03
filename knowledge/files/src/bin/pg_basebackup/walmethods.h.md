# walmethods.h

## Purpose

Defines the pluggable "WAL writer method" interface used by
`receivelog.c` so the streaming receive loop doesn't need to know
whether WAL segments are landing as individual files in a directory
(`pg_basebackup` plain-format, `pg_receivewal`) or as a single tar
archive (`pg_basebackup --format=t`).

## Key types

- `Walfile` (lines 17-29) — the opaque file handle. Each method
  embeds this as the first member of a method-specific struct
  (`DirectoryMethodFile`, `TarMethodFile`) — a hand-rolled vtable
  pattern.
- `WalCloseMethod` enum (lines 31-36): `CLOSE_NORMAL`, `CLOSE_UNLINK`
  (delete on close, used on error), `CLOSE_NO_RENAME` (keep the
  `.partial` suffix because the segment is incomplete).
- `WalWriteMethodOps` (lines 41-93) — the vtable: `open_for_write`,
  `close`, `existsfile`, `get_file_size`, `get_file_name`, `write`,
  `sync`, `finish`, `free`. Notable that `existsfile` and
  `get_file_size` are tar-method no-ops (it pretends nothing exists,
  because it's writing-only).
- `WalWriteMethod` (lines 103-118) — the base method struct with
  compression alg/level, sync flag, and a `lasterrstring` /
  `lasterrno` pair for the unified error-reporting protocol.

## Public functions

- `CreateWalDirectoryMethod(basedir, alg, level, sync)` — line 127.
  Writes one file per WAL segment, optionally compressed (gzip or
  lz4). Used by `pg_receivewal` and by `pg_basebackup`'s plain-format
  WAL stream.
- `CreateWalTarMethod(tarbase, alg, level, sync)` — line 130.
  Writes one `.tar` (or `.tar.gz`) containing the WAL segments.
  "Only implements the methods required for pg_basebackup, not all
  those required for pg_receivewal" — comment line 124-125.
- `GetLastWalMethodError(wwmethod)` — returns `lasterrstring` if set,
  else `strerror(lasterrno)`. Line 134.

## Phase D notes

- The error-string pair is set by every method's failure path
  (`wwmethod->lasterrstring = …` or `wwmethod->lasterrno = errno`).
  The contract per the header comment line 99-101 is that
  `lasterrstring` takes precedence. Methods MUST call `clear_error()`
  at the top of each operation; that's the only thing preventing a
  stale error from leaking out. [verified-by-code from walmethods.c]
- No checksum / integrity field — the writer methods don't verify
  what `receivelog.c` hands them. Trust boundary is the server →
  network → receivelog path; walmethods is downstream. [inferred]
