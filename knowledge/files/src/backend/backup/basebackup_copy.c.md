# `src/backend/backup/basebackup_copy.c`

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/backend/backup/basebackup_copy.c`

## Purpose

`bbsink` that streams archives (and the manifest) to the connected client
via a single `COPY OUT` operation. Sends a tablespace info result set
first, then enters COPY mode; each CopyData message starts with a type byte
so archives and the manifest can be multiplexed inside one COPY stream.
The old "one COPY per archive" protocol is no longer supported.
[from-comment] (`basebackup_copy.c:3-17`)

## Surface

- `bbsink_copystream_new(bool send_to_client)` (`basebackup_copy.c:108`) —
  factory.
- Standard `bbsink` callbacks: `bbsink_copystream_{begin_backup,
  begin_archive, archive_contents, end_archive, begin_manifest,
  manifest_contents, end_manifest}`.

## Notes

When `send_to_client` is false the sink is a no-op transport (used by
server-side backup which terminates the chain locally). `archive_contents`
emits a 'd' (archive data) type byte; `manifest_contents` emits 'm'.

## Tag tally

`[from-comment]` 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
