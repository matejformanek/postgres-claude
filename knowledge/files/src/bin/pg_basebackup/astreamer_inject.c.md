# astreamer_inject.c

## Purpose

Implements the recovery-config-injector astreamer used by
`pg_basebackup -R`: rewrites the server's tar stream so the extracted
cluster can come up as a standby. Also exports the generic
`astreamer_inject_file()` helper used by `pg_basebackup.c` to inject the
backup manifest and signal files.

## Role in pg_basebackup

Last-mile rewriter on the recv pipeline. The chain (per
`CreateBackupStreamer()` in `pg_basebackup.c:1063`) is:

```
server COPY-data
  → astreamer_tar_parser
    → astreamer_recovery_injector   ← THIS FILE
      → astreamer_tar_archiver / extractor
        → writer (plain / gzip / lz4 / zstd)
```

## Wire/protocol surface

Consumes already-parsed tar member events (`ASTREAMER_MEMBER_HEADER`,
`*_CONTENTS`, `*_TRAILER`, `ASTREAMER_ARCHIVE_TRAILER`). It does not
parse raw bytes; the upstream parser has already validated the tar
structure. The injector ONLY matches member pathnames by exact
`strcmp` against `"standby.signal"`, `"postgresql.auto.conf"`, and
`"recovery.conf"`. `astreamer_inject.c:108,110,131`

## Key functions

- `astreamer_recovery_injector_new()` `astreamer_inject.c:64` — allocates
  the wrapper and stores the recovery-config buffer (no copy: caller
  must keep it alive until the streamer is freed). [verified-by-code]
- `astreamer_recovery_injector_content()` `astreamer_inject.c:84` — the
  three-case rewriter:
  1. On v12+, suppress any incoming `standby.signal` (we'll inject our
     own at end of archive) and append our content to
     `postgresql.auto.conf`. To make the trailing append work, the
     incoming header is zeroed (`data = NULL; len = 0;` line 125-126)
     and the recorded `member.size` is bumped by the append length —
     a successor streamer (`astreamer_tar_archiver`) regenerates the
     header from `member`. `astreamer_inject.c:111-128`
  2. On older versions, suppress `recovery.conf` from the stream and
     inject our own at archive end. `astreamer_inject.c:131,176-182`
  3. `ASTREAMER_ARCHIVE_TRAILER` is where the final injections happen
     (`postgresql.auto.conf` if not already seen + empty
     `standby.signal`). `astreamer_inject.c:157-185`
- `astreamer_inject_file()` `astreamer_inject.c:218` — synthesizes a
  three-event sequence (`HEADER`, `CONTENTS`, `TRAILER`) for one fake
  tar member. Hard-codes `mode = pg_file_create_mode`, `uid = 04000`,
  `gid = 02000` ("no principled argument…but historical" — line 234).
  `is_regular = true`, no symlink. [verified-by-code]

## State / globals

`astreamer_recovery_injector` struct (lines 18-27):

- `skip_file` — currently-in-progress member is being filtered out
- `is_postgresql_auto_conf` / `found_postgresql_auto_conf` — track the
  v12+ append case
- `member` — a *copy* of the upstream member descriptor, mutated to
  reflect bumped size

No file-scope globals. Each injector instance is per-pipeline-chain.

## Phase D notes

[ISSUE-trust-boundary: server-controlled tar member name decides
whether content gets injected after, before, or as a replacement
(maybe)] — If the server sent a tarball with an extra adversarial
`postgresql.auto.conf` member, the injector would suppress the rest
of *its own* content (zeroing the header) and append ours to the
already-suppressed body, producing a file whose content is just our
recovery config. That's actually desirable behavior. But a more
subtle question is what happens if the server omits or duplicates
the file: the code at line 165 (`found_postgresql_auto_conf`) only
checks the *boolean*, not a count, so duplicate
`postgresql.auto.conf` headers in the same tar would be processed
without warning (each one bumped + appended). This is unlikely to
cause harm given the server is trusted, but it's an undocumented
invariant. [inferred]

[ISSUE-undocumented-invariant: hard-coded uid=04000, gid=02000 in
`astreamer_inject_file` (info-disclosure, low)] — Comment at line
234 says "no principled argument…historical". Files extracted to
disk inherit pg_file_create_mode via dir_open_for_write, but the
*tar* metadata in any `--format=tar` output ships these magic owner
ids to the eventual restorer. [verified-by-code]

[ISSUE-undocumented-invariant: `member.size += recoveryconfcontents->len`
trusts upstream `astreamer_tar_archiver` to regenerate the header
(maybe)] — Line 117-118 mutates the header-record size, but the
data/len fields are zeroed (line 125-126). Comment line 122-125
explicitly notes: "some subsequent astreamer must regenerate it if
it's necessary." If a future pipeline reorders streamers and the
archiver is removed, header would be invalid. [verified-by-code]

No path traversal or symlink risk — pathnames are static string
literals in this file. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
