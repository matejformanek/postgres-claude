# `src/backend/backup/basebackup_sink.c`

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/backend/backup/basebackup_sink.c`

## Purpose

Default implementations of `bbsink` callbacks that simply forward to the
next sink in the chain. Sinks plug in front of one another so each can add
one concern (gzip, lz4, zstd, throttle, progress, target) and pass the rest
along. [from-comment] (`basebackup_sink.c:3-4`)

## Surface

For every callback in the `bbsink` vtable (begin_backup, begin_archive,
archive_contents, end_archive, begin_manifest, manifest_contents,
end_manifest, end_backup, cleanup) there is a `bbsink_forward_*` function
that asserts `sink->bbs_next != NULL` and delegates. The `begin_backup`
variant additionally aliases the next sink's buffer into the current sink
(`sink->bbs_buffer = sink->bbs_next->bbs_buffer`) — sinks that don't need
their own buffer share with their downstream neighbor.
[verified-by-code] (`basebackup_sink.c:23-32`)

## Mental model

A `bbsink` chain is essentially a Unix pipeline. The top of the chain
(usually `bbsink_throttle` then `bbsink_progress`) feeds into compression
(optional) then into the transport (`bbsink_copystream` to the client, or
`bbsink_server` to local disk, or `bbsink_blackhole` for benchmarks).

## Tag tally

`[verified-by-code]` 1 / `[from-comment]` 1
