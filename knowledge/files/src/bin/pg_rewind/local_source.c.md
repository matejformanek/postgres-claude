# local_source.c

## Purpose

Implements the `rewind_source` interface against a **local** data
directory (as opposed to the `libpq_source` variant which talks to a
running primary over the replication protocol). Used when the operator
passes `--source-pgdata=PATH`.

## Role in pg_rewind

One of two concrete `rewind_source` impls (the other is `libpq_source`).
The dispatcher in `pg_rewind.c` picks between them based on CLI flags.
Both expose the same vtable so the rest of pg_rewind doesn't care.

The local variant assumes the source is offline (or at least not
mutating) — see the "size of source file changed concurrently" check
in `local_queue_fetch_file`.

## Key functions

- `init_local_source(datadir)` (`source/src/bin/pg_rewind/local_source.c:37-55`).
  Allocates a `local_source`, populates the vtable; leaves
  `get_current_wal_insert_lsn = NULL` because there is no live primary
  to query for an in-progress LSN. Returns the embedded `rewind_source *`.
- `local_traverse_files` (`:57-61`). Thin wrapper around
  `traverse_datadir` from `file_ops.c`.
- `local_fetch_file` (`:63-67`). Thin wrapper around `slurpFile`.
- `local_queue_fetch_file(source, path, len)` (`:74-120`). Whole-file
  copy: open source, `open_target_file(path, true)` (truncate), loop
  `read` into a `PGIOAlignedBlock` and `write_target_range`. Verifies
  total bytes read matches `len`; mismatch is fatal with "changed
  concurrently" message.
- `local_queue_fetch_range(source, path, off, len)` (`:125-171`).
  Range copy: `lseek(srcfd, off)`, `open_target_file(path, false)`
  (no truncate), then loop read/write `PGIOAlignedBlock`-sized chunks.
  EOF mid-range is fatal — unlike `_fetch_file`, here the size was
  pre-committed by the filemap.
- `local_finish_fetch` (`:173-179`). No-op: ranges are flushed
  inline (no batching).
- `local_destroy` (`:181-185`). `pfree` (which on frontend is `pg_free`).

## State / globals

None besides the embedded `local_source` struct holding `const char *datadir`.

## Phase D notes

### Trust posture

The operator points pg_rewind at a local path. The operator is
presumed to trust that path. Compared to libpq_source the threat
model is narrower: no network attacker, no replication-protocol parser
bugs to worry about.

But: the local source path is read via `open(O_RDONLY)` without
`O_NOFOLLOW`. If `--source-pgdata` accidentally points at a directory
where the actual data files are symlinks (e.g. a tablespace), those
links are followed. That's the intended behaviour for pg_tblspc, but
worth flagging that the same applies anywhere else.

### Concurrent-change detection

`local_queue_fetch_file` checks that the byte count copied equals the
expected `len` from the filemap. If the source file grew/shrank
between inventory and copy, pg_rewind aborts. `local_queue_fetch_range`
treats premature EOF as fatal. Neither detects a file that has been
**rewritten in place** to a different value at the same offset — the
filemap's earlier size readout will match a same-size mutation.

### Block alignment

Uses `PGIOAlignedBlock` for the I/O buffer (`:78`, `:130`). This is
just for performance (direct-I/O friendliness); no correctness impact.

## Potential issues

- `[ISSUE-trust-boundary: source open() lacks O_NOFOLLOW (low)]`
  (`:86`, `:138`). A symlinked source file is followed. Lower severity
  than the file_ops.c write-side equivalent because reading through a
  symlink to attacker-controlled data only matters insofar as it ends
  up written to the target — which IS the whole point of pg_rewind.
  So in practice: an attacker who can plant a symlink in the source
  data dir can cause pg_rewind to copy attacker-chosen file contents
  into the target. Probably acceptable since "trust the source data
  dir" is the operator's call.
- `[ISSUE-correctness: same-size mid-run mutation of source not
  detected (low)]` (`:114-116`). Only the total byte count is checked.
  If the source mutates a block in place with the same final size,
  the copy succeeds with possibly torn / mixed-version data.
- `[ISSUE-dos: local_queue_fetch_file allocates one PGIOAlignedBlock
  on the stack per call (low)]` (`:78`). `PGIOAlignedBlock` is one
  page (8KB by default) — fine, but unbounded recursion if the
  caller misuses the API could blow the stack. Not currently an
  issue; flagged only as an invariant for refactorers.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_rewind`](../../../../issues/pg_rewind.md)
<!-- issues:auto:end -->
