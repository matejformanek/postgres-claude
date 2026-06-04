# `src/fe_utils/astreamer_tar.c`

- **File:** `source/src/fe_utils/astreamer_tar.c` (550 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Three astreamers that bridge between raw byte streams and the *typed* member
chunks the rest of the pipeline expects. (1) `astreamer_tar_parser` consumes
`ASTREAMER_UNKNOWN` raw tar bytes and splits them into typed
`ASTREAMER_MEMBER_HEADER`/`_CONTENTS`/`_TRAILER`/`ASTREAMER_ARCHIVE_TRAILER`
chunks for downstream (the inverse: tar demux). (2) `astreamer_tar_archiver`
does the reverse, regenerating tar headers/padding so an upstream streamer can
mutate member contents/sizes without understanding the tar format (tar mux).
(3) `astreamer_tar_terminator` blindly appends the two NUL blocks older servers
omit. This is the file the A4 sweep flagged as a corpus gap: it is where
**server-supplied tar member names and sizes enter the client**, so it is the
primary trust boundary for `pg_basebackup`/`pg_verifybackup`/`pg_combinebackup`.
[verified-by-code] (header comment `:1-20`, `astreamer.h` chunk conventions)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `astreamer_tar_parser_new` | :92 | Construct a tar parser; `next` receives typed chunks. Allocates `bbs_buffer`, starts in `ASTREAMER_MEMBER_HEADER` state. |
| `astreamer_tar_archiver_new` | :391 | Construct a tar archiver that regenerates headers/trailers for zero-length header chunks. |
| `astreamer_tar_terminator_new` | :497 | Construct a passthrough streamer that appends two NUL blocks at finalize. |

## Internal landmarks

- **vtables:** `astreamer_tar_parser_ops` (`:53`), `astreamer_tar_archiver_ops`
  (`:66`), `astreamer_tar_terminator_ops` (`:79`).
- **parser struct** (`:30-37`): carries `next_context` (the state machine
  cursor), the current `astreamer_member`, `file_bytes_sent`, and
  `pad_bytes_expected`. The accumulation buffer is the base `bbs_buffer`.
- **parser content state machine** (`:110-257`) — a `while (len > 0)` loop
  switching on `next_context`:
  - `ASTREAMER_MEMBER_HEADER` (`:126`): `astreamer_buffer_until(..., TAR_BLOCK_SIZE)`
    accumulates exactly one 512-byte block before calling
    `astreamer_tar_header()` (`:132-142`). On a zero-size member it emits a
    zero-length `_TRAILER` immediately and loops back to expect the next header
    (`:144-154`); otherwise it switches to `_CONTENTS` (`:157-159`). Resets
    `bbs_buffer.len = 0` and `file_bytes_sent = 0` (`:160-161`).
  - `ASTREAMER_MEMBER_CONTENTS` (`:167`): forwards at most
    `member.size - file_bytes_sent` bytes (`Min(nbytes, len)`, `:174-175`) as a
    `_CONTENTS` chunk, advances `file_bytes_sent` (`:177-183`). When the whole
    member has been sent it either emits a zero-length `_TRAILER` (no padding)
    or switches to `_TRAILER` to collect padding (`:191-209`). **The
    server-supplied `member.size` is the sole authority for how many input
    bytes belong to this member.** [verified-by-code]
  - `ASTREAMER_MEMBER_TRAILER` (`:213`): buffers exactly
    `pad_bytes_expected` padding bytes, forwards them as a `_TRAILER`, returns
    to `_HEADER` (`:220-233`).
  - `ASTREAMER_ARCHIVE_TRAILER` (`:236`): after the two zero blocks, buffers
    *all* remaining bytes (POSIX last-block padding / GNU 10 kB pad) and returns;
    they are flushed at finalize (`:249-250`). [from-comment]
- **`astreamer_tar_header`** (`:266-348`) — parses one 512-byte block:
  - Detects the all-zero end-of-archive block by scanning all
    `TAR_BLOCK_SIZE` bytes; returns `false` (→ `ARCHIVE_TRAILER`) if so
    (`:279-294`).
  - `isValidTarHeader(buffer)` checksum/format validation, else
    `pg_fatal("...not...a valid tar archive")` (`:299-300`).
  - `strlcpy(member->pathname, &buffer[TAR_OFFSET_NAME], MAXPGPATH)` (`:305`),
    rejects empty name (`:306-307`), then **enforces
    `path_is_safe_for_extraction(member->pathname)`** with `pg_fatal` on failure
    (`:308-310`). This is the first path-safety gate; the extractor re-checks.
    [verified-by-code]
  - `member->size/mode/uid/gid` via `read_tar_number` (`:312-315`); type flag
    dispatch sets `is_regular`/`is_directory`/`is_symlink`, copies a ≤100-byte
    `linktarget` for symlinks, and `pg_fatal`s on PAX extended headers
    (`:317-337`).
  - `pad_bytes_expected = tarPaddingBytesRequired(member->size)` (`:340`), then
    forwards the *unmodified* 512-byte header downstream as `_HEADER` (`:343-345`).
- **parser finalize** (`:353-370`): `pg_fatal("COPY stream ended before last
  file was finished")` unless cleanly at an archive trailer or an empty header
  boundary (`:358-361`); emits the buffered `ARCHIVE_TRAILER` then finalizes the
  successor. [verified-by-code]
- **parser free** (`:375-381`): frees `bbs_buffer.data`, the successor, then self.
- **archiver content** (`:425-472`): if a `_HEADER` chunk has `len != TAR_BLOCK_SIZE`
  (asserted `== 0`), it builds a fresh header via `tarCreateHeader(buffer,
  member->pathname, NULL, member->size, member->mode, ...)` into a
  `2*TAR_BLOCK_SIZE` stack buffer and sets `rearchive_member = true`
  (`:436-448`). A following `_TRAILER` while `rearchive_member` is regenerated
  as `tarPaddingBytesRequired(member->size)` zero bytes (`:450-461`). An
  `ARCHIVE_TRAILER` is always replaced with two zero blocks (`:463-469`).
  Everything else passes through (`:471`). [verified-by-code]
- **terminator** (`:513-540`): content is pure passthrough; finalize emits
  `2*TAR_BLOCK_SIZE` NUL bytes then finalizes the successor.

## Invariants & gotchas

- **512-byte block alignment.** Headers and padding are always quantized to
  `TAR_BLOCK_SIZE` (512). The parser refuses to act on a header until a full
  block is buffered (`:132`); `astreamer_tar_header` asserts
  `bbs_buffer.len == TAR_BLOCK_SIZE` (`:274`). [verified-by-code]
- **Server-supplied size drives the demux, not an allocation.** `member.size`
  bounds how many bytes are forwarded per member (`:174`) and the padding count
  (`:340`); it is *not* used to size any client-side buffer here — content is
  forwarded in input-sized slices, so a huge `size` does not cause a large
  allocation in the parser itself. (Contrast the extractor, which `fwrite`s the
  forwarded bytes to disk.) [verified-by-code]
- **Path safety enforced at parse time.** Empty names and
  non-`path_is_safe_for_extraction` names are fatal here (`:306-310`), before
  any downstream streamer sees the member. The extractor in `astreamer_file.c`
  repeats the check (defense in depth). [verified-by-code]
- **PAX unsupported.** Extended headers (`x`/`g`) are a hard `pg_fatal`
  (`:330-333`); the parser never honors a PAX long-name/size override, so the
  100-byte legacy name and 12-byte octal size fields are authoritative. This
  closes the classic "PAX path overrides the safe ustar name" traversal vector.
  [verified-by-code]
- **`linktarget` truncation.** Only 100 bytes of the link name field are copied
  (`:328`); longer GNU/`L` long-link targets are not assembled (no GNU longlink
  typeflag handling). [verified-by-code]
- **Frontend memory:** `palloc0_object`/`initStringInfo`/`pfree`; errors via
  `pg_fatal`. The archiver and terminator use fixed `2*TAR_BLOCK_SIZE` stack
  buffers (`:432`, `:534`). [verified-by-code]
- **Buffer ownership:** the parser owns `bbs_buffer`; `bbs_buffer.len` is reset
  to 0 at each state transition rather than the data being freed (`:160`,
  `:209`, `:233`). [verified-by-code]

## Cross-references

- `knowledge/files/src/fe_utils/astreamer_file.c.md` — the extractor/plain-writer
  sinks that consume the typed chunks this parser emits; the extractor re-runs
  `path_is_safe_for_extraction`.
- `source/src/include/fe_utils/astreamer.h:62-91` — `astreamer_archive_context`
  enum, `astreamer_member` descriptor, `astreamer_buffer_until`/`_buffer_bytes`.
- `path_is_safe_for_extraction` — `source/src/port/path.c` (canonicalize then
  `path_is_relative_and_below_cwd`). [inferred from call site]
- `isValidTarHeader` / `read_tar_number` / `tarCreateHeader` /
  `tarPaddingBytesRequired` — `source/src/port/tar.c`, `source/src/include/pgtar.h`.
- `knowledge/files/src/bin/pg_basebackup/astreamer_inject.c.md` — sits between
  parser and archiver in `CreateBackupStreamer()`.

## Potential issues

- **[ISSUE-undocumented-invariant: client fully trusts server tar metadata]**
  `astreamer_tar.c:305-315` — member name, size, mode, uid, gid, and type are
  read verbatim from the server-sent tar block and propagated downstream (the
  extractor then `mkdir`/`fopen`/`chmod`s with the server-chosen `mode`). The
  only validation is `isValidTarHeader` (format/checksum), a non-empty name, and
  `path_is_safe_for_extraction`. This is by design — for base backups the server
  is the trust root — but it is the concrete realization of the A4
  "trust-the-stream" finding and deserves an explicit invariant note: a
  compromised/hostile server controls every extracted file's path-within-tree,
  permissions, and ownership bits. (maybe)
- **[ISSUE-question: `member.size` is unvalidated against any ceiling]**
  `astreamer_tar.c:312` — `read_tar_number` yields a `size_t`; the parser
  imposes no upper bound. It does not over-allocate (content is streamed in
  input-sized slices), but the value flows to `tarPaddingBytesRequired` and into
  the extractor's per-member `fwrite` loop, so a malicious server can make the
  client write arbitrarily large files. This is the disk-exhaustion analogue of
  the A5 decompression-bomb theme rather than a memory bomb. (nit)

## Confidence tag tally

- `[verified-by-code]` × 18
- `[from-comment]` × 2
- `[inferred]` × 1
