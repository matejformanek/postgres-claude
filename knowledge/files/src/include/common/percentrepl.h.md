# src/include/common/percentrepl.h

## Purpose

Single-function header for the variadic `%`-substitution helper used
by GUCs that take command templates: `archive_command`,
`restore_command`, `archive_cleanup_command`, `recovery_end_command`.

## Role in PG

Shared **frontend + backend** — `pg_archivecleanup` uses the same
helper as the server.

## Key declarations

- `extern char *replace_percent_placeholders(const char *instr,
  const char *param_name, const char *letters, ...)`
  (`percentrepl.h:16`)

## Phase D notes

The substituted output is fed straight to `system(3)` /
`OpenPipeStream()` in the archive/restore command path. The helper
itself does NOT shell-escape — see `percentrepl.c.md` and the GUC
documentation. Any quote in a placeholder value (filename, path)
inherits the trust level of whoever produced it; for archive paths
this is internal, but it is a documented "do not point at
user-controlled filenames" boundary.

## Potential issues

None at the header level — semantics live in the .c.
