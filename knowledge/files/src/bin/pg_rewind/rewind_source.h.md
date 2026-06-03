# rewind_source.h

**Source:** `source/src/bin/pg_rewind/rewind_source.h` (86 lines)

## Purpose

Defines the `rewind_source` abstract interface — a vtable of seven
function pointers that decouples `pg_rewind.c` from whether the source
is a remote libpq connection or a local data directory. Concrete
implementations live in `libpq_source.c` and `local_source.c`.
[verified-by-code]

## Role in pg_rewind

`main()` picks the implementation in one branch: `init_libpq_source(conn)`
if `--source-server=` was given, otherwise `init_local_source(datadir_source)`
(`pg_rewind.c:309-322`). Every subsequent fetch — file listing,
single-file slurp, queued range fetches, and the current-WAL-insert
LSN probe — goes through the vtable. This is the trust boundary:
everything below this interface is "data from the source"; everything
above it is supposed-to-be-validated bytes written to the target.
[verified-by-code]

## Vtable members

- `traverse_files(source, callback)` — feeds every file in the source
  data directory to `process_source_file()` (`filemap.c:280`).
  [verified-by-code]
- `fetch_file(source, path, *filesize)` — slurp a whole file into a
  malloc'd, zero-terminated buffer. Used for `XLOG_CONTROL_FILE` and
  for timeline-history files (`pg_rewind.c:349,648,891`).
  [verified-by-code]
- `queue_fetch_range(source, path, offset, len)` — enqueue a partial
  read; libpq impl batches up to `MAX_CHUNKS_PER_QUERY` requests.
  [verified-by-code]
- `queue_fetch_file(source, path, len)` — enqueue a whole-file copy.
  The libpq impl truncates the target immediately and queues
  `Max(len, MAX_CHUNK_SIZE)` so a file enlarged after directory scan
  is still fetched in full up to 1 MiB (`libpq_source.c:347-348`).
  [verified-by-code]
- `finish_fetch(source)` — flush the queue.
- `get_current_wal_insert_lsn(source)` — only meaningful for the
  libpq impl. The local impl reads from `pg_control` instead.
  [from-comment]
- `destroy(source)` — free the source object. NOTE: libpq impl does
  **not** close the PGconn it borrowed (`libpq_source.c:683-684`).
  [verified-by-code]

## Phase D notes

The interface is honest about its trust shape: the comment for
`queue_fetch_file` (`rewind_source.h:52-59`) explicitly says
"the implementation should try to copy the whole file, even if it's
larger than expected" — i.e. the source is allowed to lie about size
and the client compensates. There is no checksum or signature on
fetched bytes; the assumption is that the libpq channel is trusted
(authenticated + optionally TLS) and the source server is benign.

The vtable does not split read-only metadata from bulk byte fetches,
so a hostile source that authenticates as a low-privilege user but
serves attacker bytes is not distinguishable at this layer from a
normal source.

## Potential issues

- `[ISSUE-trust-boundary: vtable comment for queue_fetch_file admits the source may report a wrong size and the implementation should fetch more if needed; no protection against a source claiming size=0 for a large file so that target gets truncated to 0 (medium)]`
- `[ISSUE-undocumented-invariant: destroy() comment says it does not close the PGconn, but only the libpq impl. A future caller swapping impls could leak or double-close (low)]`
- `[ISSUE-trust-boundary: no integrity check (checksum/HMAC) at this layer; correctness relies entirely on transport security and the source-server's privilege model (maybe)]`
