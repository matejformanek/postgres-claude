---
source_url: https://www.postgresql.org/docs/current/basic-archive.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — basic_archive (the archive-module example)

`contrib/basic_archive` is the reference implementation of the **archive module**
API (loaded via `archive_library`, the modern alternative to a shell
`archive_command`). It copies each completed WAL segment to a directory,
crash-safely. Read it as the template for any custom archiver. `[from-docs]`

## The module API (verified against source)

- Entry point `_PG_archive_module_init(void)` returns a
  `const ArchiveModuleCallbacks *` (`source/contrib/basic_archive/basic_archive.c:84-85`).
  `[verified-by-code]`
- The callback struct is `static const ArchiveModuleCallbacks
  basic_archive_callbacks = { .startup_cb = NULL, .check_configured_cb =
  basic_archive_configured, .archive_file_cb = basic_archive_file, .shutdown_cb =
  NULL }` (`basic_archive.c:52-56`). `[verified-by-code]` So a minimal archiver
  needs only **check_configured** + **archive_file**; startup/shutdown are
  optional.
- `check_configured_cb` gates archiving on configuration being present (here, the
  directory GUC); the server won't call `archive_file_cb` until it returns true.
  `[verified-by-code]`

## Loading & configuration

- Load via **`archive_library = 'basic_archive'`** (NOT `archive_command`), and
  `archive_mode` must be `on`. `[from-docs]`
- GUC `basic_archive.archive_directory` (a `DefineCustomStringVariable`,
  `basic_archive.c:67`); the directory must already exist; empty string halts
  archiving. `[verified-by-code]`

## The crash-safety mechanism (verified against source)

- `basic_archive_file` first **refuses to overwrite** an existing destination
  unless the bytes are identical: `if (compare_files(path, destination))` returns
  success (already archived) at `:166`; `compare_files` is the byte comparator at
  `:225`. `[verified-by-code]`
- It writes to a temporary name `archtemp.<file>.<pid>.<epoch>`
  (`snprintf(..., "archtemp", file, MyProcPid, epoch)`, `:198`), `copy_file`s into
  it (`:204`), then **`durable_rename(temp, destination, ERROR)`** (`:211`) — the
  atomic, fsync'd publish that prevents a torn/partial WAL file from ever
  appearing under its real name. `[verified-by-code]`
- Consequence the docs call out: a **server crash mid-archive can leave
  `archtemp`-prefixed files** in the directory; they are safe to remove.
  `[from-docs]`
- It is a starting-point template, not a production archiver. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/archive-module-callbacks.md]]` — the
  `ArchiveModuleCallbacks` contract this module fills (the prose spec).
- `[[knowledge/docs-distilled/pgprewarm.md]]` — same crash-safe "temp file +
  `durable_rename`" idiom in the autoprewarm dump path.
- `[[knowledge/docs-distilled/wal-internals.md]]` / `[[knowledge/docs-distilled/runtime-config-wal.md]]`
  — WAL segment lifecycle / `archive_mode` semantics archiving hooks into.
- Skills: `wal-and-xlog`, `bgworker-and-extensions` (module loading), `gucs-config`.
