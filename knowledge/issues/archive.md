# Issues — `archive`

Per-subsystem issue register for `src/backend/archive/` — the
built-in shell_archive module backing `archive_command`.

**Parent subsystem docs:**
- `knowledge/files/src/backend/archive/shell_archive.c.md`
- Sibling: `knowledge/issues/basic_archive.md` (contrib sample module)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | archive/shell_archive.c:79 | style | nit | `fflush(NULL)` flushes ALL stdio streams before every `system()` call. Necessary to avoid double-flush across fork, but a perf nit in heavy-archiving workloads | open | knowledge/files/src/backend/archive/shell_archive.c.md §Potential issues |
| 2026-06-11 | archive/shell_archive.c:129,133 | style | nit | Both error paths in `shell_archive_file` `pfree(xlogarchcmd)` — could collapse to one trailing `pfree` after the if-else | open | knowledge/files/src/backend/archive/shell_archive.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- The `ArchiveModuleCallbacks` interface (in `archive/archive_module.h`)
  is the extension point for custom archive backends; `shell_archive`
  is the default. `archive_library` GUC selects between them.
- `wait_result_is_any_signal(rc, true)` classifying signal-exits as
  FATAL (rather than LOG) is the explicit policy choice: SIGINT /
  SIGQUIT to the archiver implies the operator wants the postmaster
  to notice. Comment: "If we overreact it's no big deal, the
  postmaster will just start the archiver again."
- `%f` / `%p` substitution is centralised in
  `src/common/percentrepl.c`'s `replace_percent_placeholders` — same
  helper used by `restore_command`.
