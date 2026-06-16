# `src/backend/archive/shell_archive.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~145
- **Source:** `source/src/backend/archive/shell_archive.c`

The built-in `archive_command`-based archive module. This is the
default WAL archive backend; other modules implementing the same
`ArchiveModuleCallbacks` interface (`archive/archive_module.h`) can
be loaded via `archive_library`. [verified-by-code §shell_archive.c:1-15]

## API / entry points

- `const ArchiveModuleCallbacks *shell_archive_init(void)` — returns a
  static `ArchiveModuleCallbacks` struct with only
  `check_configured_cb`, `archive_file_cb`, `shutdown_cb` set
  (no `startup_cb`). [verified-by-code §shell_archive.c:33-44]
- `static bool shell_archive_configured(...)` — true iff
  `XLogArchiveCommand[0] != '\0'`. Reports a structured errdetail
  via `arch_module_check_errdetail` when not configured.
  [verified-by-code §shell_archive.c:46-55]
- `static bool shell_archive_file(state, file, path)` — the actual
  archiver:
  1. `replace_percent_placeholders(XLogArchiveCommand, ..., "fp",
     file, nativePath)` expands `%f` and `%p`.
  2. `fflush(NULL)` to push stdio buffers before fork.
  3. `pgstat_report_wait_start(WAIT_EVENT_ARCHIVE_COMMAND)` →
     `system(cmd)` → `pgstat_report_wait_end()`.
  4. On non-zero exit, classify via `WIFEXITED` / `WIFSIGNALED`,
     and pick FATAL or LOG based on `wait_result_is_any_signal(rc, true)`
     — signal exits trigger a FATAL because SIGINT/SIGQUIT to the
     archiver implies the operator wants us to stop too.
  [verified-by-code §shell_archive.c:57-137, from-comment §shell_archive.c:86-93]
- `static void shell_archive_shutdown(state)` — DEBUG1 trace.
  [verified-by-code §shell_archive.c:139-143]

## Notable invariants / details

- **Native path conversion.** `nativePath = pstrdup(path); make_native_path(nativePath);`
  converts forward slashes to backslashes on Windows before %p is
  substituted. [verified-by-code §shell_archive.c:65-69]
- **`replace_percent_placeholders`** centralises the `%f` /`%p`
  expansion (and the literal `%%` escape) for both archive and
  restore commands. Lives in `src/common/percentrepl.c`.
  [verified-by-code §shell_archive.c:71-74]
- **Signal-exit ⇒ FATAL.** `wait_result_is_any_signal(rc, true)` —
  the `true` means "treat SIGTERM as a signal exit". Comment:
  "system() ignores SIGINT and SIGQUIT while waiting; so a signal is
  very likely something that should have interrupted us too. ... If
  we overreact it's no big deal, the postmaster will just start the
  archiver again." [from-comment §shell_archive.c:86-93]
- **Windows exception path** reports the WTERMSIG value as a hex
  status code with `errhint("See C include file \"ntstatus.h\" for a
  description of the hexadecimal value.")`. [verified-by-code §shell_archive.c:106-112]

## Potential issues

- **File-line `shell_archive.c:79`.** `fflush(NULL)` flushes ALL
  stdio streams before `system()`. This is necessary to avoid
  double-flushing across fork, but in heavy-archiving workloads it
  can be a perf nit. Not actionable. [ISSUE-style: fflush-NULL on every WAL segment (nit)]
- **File-line `shell_archive.c:129, 133`.** Both error paths pfree
  `xlogarchcmd`. The structure is mildly duplicative — could be one
  trailing `pfree(xlogarchcmd)` after the if-else. Cosmetic.
  [ISSUE-style: duplicate pfree branches (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `archive`](../../../../issues/archive.md)
<!-- issues:auto:end -->
