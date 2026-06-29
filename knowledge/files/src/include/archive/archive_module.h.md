# `src/include/archive/archive_module.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~67
- **Source:** `source/src/include/archive/archive_module.h`

Archive-module loadable interface (added PG 15). Replaces the
hard-coded `archive_command` shell-out with a pluggable C library
loaded via the `archive_library` GUC; the module returns a struct of
callbacks from `_PG_archive_module_init`. `basic_archive` (contrib)
and `shell_archive` (in-tree, see `shell_archive.h`) are both built
on this. [verified-by-code]

## API / declarations

- `extern PGDLLIMPORT char *XLogArchiveLibrary;` — value of the
  `archive_library` GUC.
- `ArchiveModuleState { void *private_data }` — opaque
  per-archiver state passed through every callback. Modules
  attach their own state here in `startup_cb`.
- Callback typedefs:
  - `ArchiveStartupCB(state)` — called once after load.
  - `ArchiveCheckConfiguredCB(state)` → bool — should we run? Used
    to skip archiving when configuration is incomplete.
  - `ArchiveFileCB(state, file, path)` → bool — the **only
    required** callback. Returns true on success, false on
    transient failure (PG retries).
  - `ArchiveShutdownCB(state)` — called on archiver shutdown.
- `ArchiveModuleCallbacks { startup_cb, check_configured_cb,
  archive_file_cb, shutdown_cb }`.
- `ArchiveModuleInit` — type of `_PG_archive_module_init`.
- `extern PGDLLEXPORT const ArchiveModuleCallbacks
  *_PG_archive_module_init(void);` — the exported entry symbol an
  archive .so must define.

### Error-message support

- `extern PGDLLIMPORT char *arch_module_check_errdetail_string;`
- `arch_module_check_errdetail` macro — wraps a
  `pre_format_elog_string` call so a module can stash a formatted
  errdetail string before raising. The macro EXPANDS to a comma
  expression — used as the `errdetail(...)` arg in `ereport`.
  [verified-by-code]

## Notable invariants / details

- "`ArchiveFileCB` is the only required callback." All others may
  be NULL. [from-comment]
- The module is loaded into the archiver subprocess (NOT a
  postmaster) — it can use blocking I/O without affecting other
  backends.
- `check_configured_cb` is what lets `basic_archive` log a NOTICE
  about a missing target directory instead of repeatedly trying
  and failing. [inferred]

## Potential issues

- Comment says "the archive modules documentation" for callback
  semantics — but the only callback table here doesn't link to it.
  [ISSUE-doc-drift: callback semantics in sgml only (nit)]
- Module ABI has no version field; an .so built against PG 16's
  `ArchiveModuleCallbacks` and loaded into PG 17 with added
  callbacks would read past the end of the returned struct. The
  init function returns a `const *`, so reordering would silently
  miscall. [ISSUE-undocumented-invariant: archive ABI version
  field absent (likely)]
- `arch_module_check_errdetail` is a macro that expands to a comma
  expression with `errno` evaluated once — works only when used as
  the argument to a function-like helper. Misuse is silent.
  [ISSUE-style: comma-expression macro (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `archive`](../../../../issues/archive.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-basic_archive.md](../../../../subsystems/contrib-basic_archive.md)
