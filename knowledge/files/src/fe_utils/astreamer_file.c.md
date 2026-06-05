# `src/fe_utils/astreamer_file.c`

- **File:** `source/src/fe_utils/astreamer_file.c` (413 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

Terminal (sink) astreamers that land a backup stream on disk. Two
implementations: `astreamer_plain_writer` writes a whole archive to a single
`FILE` (used for `--format=tar` output), and `astreamer_extractor` writes each
parsed tar member out to its own file/dir/symlink under a base directory (used
for `--format=plain`). The extractor sits at the tail of a parsed chain
(`astreamer_tar_parser` → … → `astreamer_extractor`) and consumes typed chunks
(`ASTREAMER_MEMBER_HEADER`/`_CONTENTS`/`_TRAILER`); the plain writer can sit
anywhere and consumes raw bytes. Both are leaf nodes: `bbs_next == NULL`
(`astreamer_file.c:159`, `:213`). [verified-by-code]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `astreamer_plain_writer_new` | :80 | Construct a single-file writer; opens `pathname` if `file==NULL`, else writes to caller's `FILE`. |
| `astreamer_extractor_new` | :185 | Construct an extractor rooted at `basepath`, with optional `link_map` (tablespace remap) and `report_output_file` hooks. |

## Internal landmarks

- **vtables:** `astreamer_plain_writer_ops` (`:49`) and
  `astreamer_extractor_ops` (`:65`), each wiring `content`/`finalize`/`free`.
- **plain writer content** (`:106`): no-op on `len==0` (`:115`); a single
  `fwrite(data, len, 1, file)`; on short write with `errno==0` assumes `ENOSPC`
  then `pg_fatal` (`:119-126`). [verified-by-code]
- **plain writer finalize** (`:133`): `fclose` only if `should_close_file`
  (i.e. we opened it), never the caller's `FILE` (`:140`). [verified-by-code]
- **extractor content state machine** (`:205`), dispatched on
  `astreamer_archive_context`:
  - `ASTREAMER_MEMBER_HEADER` (`:218`): asserts no file currently open; calls
    `path_is_safe_for_extraction(member->pathname)` and `pg_fatal`s on failure
    (`:221-223`); builds `filename = "<basepath>/<pathname>"` via `snprintf`
    (`:226`); strips a trailing `/` (`:230-232`); then dispatches on member
    type to `create_file_for_extract` / `extract_directory` / `extract_link`
    (`:235-256`). [verified-by-code]
  - `ASTREAMER_MEMBER_CONTENTS` (`:263`): `fwrite` into the open file, same
    `ENOSPC` idiom; silently skipped if `file==NULL` (special filetype that
    opened nothing) (`:264-275`). [verified-by-code]
  - `ASTREAMER_MEMBER_TRAILER` (`:278`): `fclose` and clear `file` (`:281-284`).
  - `ASTREAMER_ARCHIVE_TRAILER` (`:287`): nothing.
- **symlink safety** (`:241-256`): the link target is first run through
  `link_map` (the `--tablespace-mapping` hook) if present; then, unless it is
  an absolute path, the *original* `member->linktarget` must pass
  `path_is_safe_for_extraction`, else `pg_fatal` (`:248-253`). Note absolute
  targets are accepted without the safety check — see Invariants. [verified-by-code]
- **`should_allow_existing_directory`** (`:308`): whitelists `EEXIST` for
  `pg_wal`/`pg_xlog`/`archive_status`/`summaries`/`pg_tblspc` and numeric
  tablespace OID dirs directly under `pg_tblspc/` (`:313-325`). [verified-by-code]
- **`extract_directory`** (`:333`): `mkdir` with `pg_dir_create_mode`, tolerate
  EEXIST per above, then `chmod` to the member's `mode` (non-WIN32). [verified-by-code]
- **`extract_link`** (`:358`): bare `symlink(linktarget, filename)`. [verified-by-code]
- **`create_file_for_extract`** (`:371`): `fopen(filename,"wb")` then `chmod`
  to member mode (non-WIN32). [verified-by-code]
- **finalize** (`:394`): assertion-only — the file handle must already be NULL.

## Invariants & gotchas

- **Frontend memory:** structs via `palloc0_object`, strings via `pstrdup`,
  released with `pfree` (`:85`, `:89`, `:161-162`, `:192`, `:411-412`). Errors
  go through `pg_fatal`. [verified-by-code]
- **Buffer ownership:** neither writer uses `bbs_buffer`; the extractor keeps a
  fixed `char filename[MAXPGPATH]` inline in its struct (`:38`). [verified-by-code]
- **Path safety is enforced here AND upstream:** the extractor independently
  re-checks `path_is_safe_for_extraction` even though `astreamer_tar_parser`
  already checked it at parse time (`astreamer_tar.c:308`). Defense in depth —
  the extractor does not *assume* its predecessor validated names. [verified-by-code]
- **`fopen`/`mkdir`/`symlink` use no `O_NOFOLLOW`/`O_EXCL`.** Extraction trusts
  that `basepath` is a fresh, attacker-free target directory. See Potential
  issues. [verified-by-code]
- **Special filetypes** (not regular/dir/symlink) open no file; subsequent
  `_CONTENTS` chunks are dropped (`:264`). [verified-by-code]
- **`fwrite(data,len,1,...)` returns 1 on success**, hence the `!= 1` test; on
  a partial/zero element write with unset `errno`, ENOSPC is assumed — a known
  PG idiom to avoid a misleading "Success" `%m`. [verified-by-code]

## Cross-references

- `knowledge/files/src/bin/pg_basebackup/astreamer_inject.c.md` — the injector
  that sits just upstream of the extractor/archiver in `CreateBackupStreamer()`.
- `knowledge/files/src/fe_utils/astreamer_tar.c.md` — produces the typed member
  chunks this extractor consumes; performs the first path-safety check.
- `path_is_safe_for_extraction` — `source/src/port/path.c:637`
  (canonicalizes, then `path_is_relative_and_below_cwd`). [verified-by-code]
- `source/src/include/fe_utils/astreamer.h:62-91` — `astreamer_archive_context`
  enum and `astreamer_member` descriptor.

## Potential issues

- **[ISSUE-question: absolute symlink targets bypass the path-safety check]**
  `astreamer_file.c:248` — `if (!is_absolute_path(linktarget) && !path_is_safe_for_extraction(...))`.
  An absolute `linktarget` (possibly produced by `link_map`/`--tablespace-mapping`)
  is short-circuited past `path_is_safe_for_extraction` and handed straight to
  `symlink()` (`:255`, `:361`). This is intentional for tablespace links
  (mappings legitimately point at absolute locations) and the comment at
  `:350-357` acknowledges the mapping is applied "blindly", but it means a
  server that emits an absolute symlink target writes an arbitrary-target
  symlink under `basepath`. Subsequent same-run `_CONTENTS` cannot follow it
  (the member is `is_symlink`, so no file is opened), but a later member whose
  path resolves through that symlink directory is constrained only by
  `path_is_safe_for_extraction` on its *own* relative name. Server is the trust
  root for base backups, so this is a defense-in-depth gap rather than a live
  bug. (maybe)
- **[ISSUE-question: no `O_NOFOLLOW`/`O_EXCL` on extracted file/dir creation]**
  `astreamer_file.c:336,361,376` — extraction into a pre-populated or
  concurrently-mutated `basepath` will follow pre-existing symlinks and
  overwrite/append existing files. Acceptable for the documented use (extract
  into an empty target dir), but worth noting alongside the A4 backup-stream-trust
  theme. (nit)

## Confidence tag tally

- `[verified-by-code]` × 17
