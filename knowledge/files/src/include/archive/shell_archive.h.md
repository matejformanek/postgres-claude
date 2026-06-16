# `src/include/archive/shell_archive.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~24
- **Source:** `source/src/include/archive/shell_archive.h`

Three-line companion to `archive_module.h` — exports the in-tree
`shell_archive_init` so the core server can install the shell-based
archiver (legacy `archive_command`) without loading a separate .so.
[verified-by-code]

## API / declarations

- `extern const ArchiveModuleCallbacks *shell_archive_init(void);`
  — same signature as `_PG_archive_module_init` but a different
  symbol; called directly from the archiver subprocess when
  `archive_library == ''` (the default). [from-comment]

## Notable invariants / details

- "Since the logic for archiving via a shell command is in the
  core server and does not need to be loaded via a shared
  library, it has a special initialization function." —
  shell_archive is statically linked in, not loaded.
  [from-comment]
- Implementation lives in `backend/archive/shell_archive.c`.

## Potential issues

- A user who renames the GUC `archive_library` to "shell" expects
  it to work — but the actual sentinel for "use the in-tree shell"
  is empty string. [ISSUE-doc-drift: archive_library = ''
  semantics not in header (nit)]
- None of substance.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `archive`](../../../../issues/archive.md)
<!-- issues:auto:end -->
