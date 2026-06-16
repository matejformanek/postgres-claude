# filemap.h

**Source:** `source/src/bin/pg_rewind/filemap.h` (124 lines)

## Purpose

Type declarations for the central pg_rewind diff data structure:
`file_entry_t` (per-file state from both source and target +
the decided action), `filemap_t` (the sorted result array), the
`file_action_t` / `file_type_t` / `file_content_type_t` enums, and
the public entry points `process_source_file`, `process_target_file`,
`process_target_wal_block_change`, `decide_file_actions`,
`calculate_totals`, `print_filemap`, plus `keepwal_init`/
`keepwal_add_entry`. [verified-by-code]

## Role in pg_rewind

This header is the contract between (a) the source / target file
walkers, (b) the WAL parser in `parsexlog.c` that calls
`process_target_wal_block_change`, and (c) the executor loop in
`perform_rewind()` that drains `filemap->entries[]` in action order.
Sorting depends on the **enum value order** of `file_action_t`
(comment at `filemap.h:16`): UNDECIDED, CREATE, COPY, COPY_TAIL,
NONE, TRUNCATE, REMOVE — so the loop creates dirs/symlinks before
copying files, truncates before removing, and removes last. The
`final_filemap_cmp` in `filemap.c:694-709` relies on this ordering.
[verified-by-code]

## Key types

- `file_action_t` — seven-valued enum, **values are
  ordering-significant** (filemap.h:16-29). [from-comment]
- `file_type_t` — REGULAR/DIRECTORY/SYMLINK (+ UNDEFINED sentinel).
  [verified-by-code]
- `file_content_type_t` — OTHER/RELATION/WAL; computed once from the
  path string (`getFileContentType` in filemap.c:567) and used to
  decide whether to track per-block changes. [verified-by-code]
- `file_entry_t` — holds both `target_*` and `source_*` (exists,
  type, size, link_target) plus a `datapagemap_t target_pages_to_overwrite`
  bitmap for the relation-file case (filemap.h:57-90). [verified-by-code]
- `filemap_t` — FLEXIBLE_ARRAY_MEMBER over `file_entry_t *`, plus
  `total_size` (source) and `fetch_size` (must-copy bytes) populated
  by `calculate_totals()` for the progress report. [verified-by-code]

## Phase D notes

The `file_entry_t.path` field is `const char *` — a `pg_strdup` of
a path that originated from either the source (libpq result row) or
the local target traversal. `filemap.h` does not declare any
validation contract on this path; that responsibility is pushed
into `file_ops.c` (where each writer calls
`path_is_safe_for_extraction()`). If a future caller added a new
write-side helper but forgot the path check, the trust shape would
silently degrade.

The `source_link_target` field is server-controlled in the libpq
case (it comes from `pg_tablespace_location()` on the source) and
gets fed directly into `symlink(link, dstpath)` in
`file_ops.c:285` with no validation of `link` itself. This is a
known trust-the-source design — tablespace symlinks point wherever
the source DBA set them.

## Potential issues

- `[ISSUE-trust-boundary: file_entry_t.source_link_target is opaque server-supplied bytes used as the target of symlink(); no validation that it is an absolute path, no length cap beyond MAXPGPATH (low)]`
- `[ISSUE-undocumented-invariant: file_action_t enum ordering is load-bearing for final_filemap_cmp; reordering by accident would silently corrupt action execution order. A static_assert would help (low)]`
- `[ISSUE-undocumented-invariant: target_pages_to_overwrite is meaningful only when content_type == FILE_CONTENT_TYPE_RELATION; not enforced at the type level (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_rewind`](../../../../issues/pg_rewind.md)
<!-- issues:auto:end -->
