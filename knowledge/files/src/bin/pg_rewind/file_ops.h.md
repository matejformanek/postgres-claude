# file_ops.h

## Purpose

Header for the file-write side of `pg_rewind`. Declares every function
that mutates the target's data directory plus the read helpers
(`slurpFile`, `traverse_datadir`) used during the discovery phase.

## Role in pg_rewind

The mutation API surface. Sources (`local_source`, `libpq_source`)
allocate file ranges to copy, then call into this header to actually
write bytes into `datadir_target`. Every write helper internally
honours the global `dry_run` flag declared in `pg_rewind.h`.

## Declared API

`source/src/bin/pg_rewind/file_ops.h:15-27`:

- Target writes: `open_target_file`, `write_target_range`,
  `close_target_file`, `remove_target_file`, `truncate_target_file`.
- Filemap-driven create/remove: `create_target(file_entry_t *)`,
  `remove_target(file_entry_t *)`.
- Whole-directory operations: `sync_target_dir()`.
- Read helpers: `slurpFile(datadir, path, *filesize)`,
  `traverse_datadir(datadir, callback)`.
- Callback type for traversal:
  `typedef void (*process_file_callback_t)(const char *path,
  file_type_t type, size_t size, const char *link_target)`.

## Phase D notes

This is the **only** header that pg_rewind code uses to write to the
target. Any auditing of attacker-influenced target writes can be
scoped to callers of these symbols.

## Potential issues

- `[ISSUE-undocumented-invariant: every write function silently
  no-ops in dry_run mode (low)]` — Declared without comments. The
  contract that all mutating ops respect `dry_run` is documented
  only in `file_ops.c`'s file header. Callers who add new write
  helpers might forget. Not a Phase D issue per se, but worth noting.
