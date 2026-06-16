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

## Issues

[ISSUE-undocumented-invariant: header does not warn that
`replace_percent_placeholders` performs NO shell escaping — output
goes to system()/OpenPipeStream() in archive_command,
restore_command, archive_cleanup_command, recovery_end_command (high)]
`percentrepl.h:16` declares the function with no contract about
escaping. A5's `common.md` finding: the .c reproduces this — a
filename / xlog path containing `'`, `;`, `$(...)`, backticks is
substituted verbatim. The GUC-boundary trust model is "only the DBA
sets these GUCs", but the .h doesn't say so. Cross-link: A14
`basebackup_to_shell` %X substitution model is the user-facing twin.

[ISSUE-trust-boundary: shared FE+BE header; same call used in
`pg_archivecleanup` (frontend) and backend recovery, multiplying
the audit surface (low)] The frontend binary may be run by a less
privileged user with attacker-influenced argv; backend executes
inside the postmaster's process tree. One signature, two threat
models.

## Cross-refs

- A5 `common.md` — GUC-boundary shell injection finding.
- A8 `archive_command` cluster — origin.
- A14 `basebackup_to_shell` — same %-substitution model in backup
  client tooling.
- Companion: `src/common/percentrepl.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->
