---
source_url: https://www.postgresql.org/docs/current/archive-module-callbacks.html
fetched_at: 2026-06-13T19:52:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Archive Module Callbacks (internals ch. 51.3)

The pluggable replacement for `archive_command`: a preloaded module that archives
WAL segments via C callbacks (in-process, no per-file shell fork). Companion to
`runtime-config-wal.md` and `wal-for-extensions.md`.

## Non-obvious claims

- **Entry point:** export `_PG_archive_module_init` returning an
  `ArchiveModuleCallbacks` struct; loaded via the **`archive_library`** GUC (the
  modern alternative to `archive_command`). [from-docs]
- **Four callbacks:** [from-docs]
  - `startup_cb(ArchiveModuleState *state)` — init after load; stash state in
    `state->private_data`.
  - `check_configured_cb(ArchiveModuleState *state) -> bool` — is the module ready
    to archive? If omitted, the server assumes always-configured.
  - `archive_file_cb(ArchiveModuleState *state, const char *file, const char *path)
    -> bool` — archive one segment (`file` = name only, `path` = full path).
  - `shutdown_cb(ArchiveModuleState *state)` — cleanup.
- **🔑 `archive_file_cb` durability contract:** return **`true`** only once the
  file is durably archived — the server may then recycle/remove the original WAL.
  Return **`false` or throw** → server keeps the WAL and **retries later**. Never
  return true before the copy is fsync'd to its destination. [from-docs]
- **`check_configured_cb` polling:** if it returns `false`, archiving pauses, the
  server logs `WARNING: archive_mode enabled, yet archiving is not configured`,
  and the server **periodically re-invokes** it until it returns `true`. Use the
  `arch_module_check_errdetail("...", ...)` macro (like `errdetail`) before
  returning false to append a reason to that warning. [from-docs]
- **Memory rule:** `archive_file_cb` runs in a **short-lived context that is reset
  between invocations** — so allocate any longer-lived state in `startup_cb` (e.g.
  a dedicated memory context), not in the per-file callback. [from-docs]
- **`shutdown_cb` fires** when the archiver process exits (including after an
  error) **or when `archive_library` changes** — enabling hot-swap of archive
  module implementations; free state to avoid leaks. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/postmaster/pgarch.c.md]] (the archiver
  process that drives these callbacks), if present.
- Idiom: [[knowledge/idioms/bgworker-and-parallel.md]] (preload / `_PG_init`-style
  module loading context), [[knowledge/idioms/error-handling.md]]
  (`errdetail`/`ereport` rules the `arch_module_check_errdetail` macro mirrors).
- Siblings: `knowledge/docs-distilled/runtime-config-wal.md`,
  `knowledge/docs-distilled/wal-for-extensions.md`,
  `knowledge/docs-distilled/custom-rmgr.md`.
- Code anchor [unverified — not line-pinned this run]:
  `source/src/include/archive/archive_module.h` (`ArchiveModuleCallbacks`,
  `ArchiveModuleState`).
