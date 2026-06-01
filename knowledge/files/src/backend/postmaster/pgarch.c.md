# pgarch.c

- **Source:** `source/src/backend/postmaster/pgarch.c` (962 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim (top comment + structure)

## Purpose

The WAL **archiver** process. Singleton aux. Polls `pg_wal/archive_status/`
for `.ready` files, hands each ready WAL segment to the configured archive
mechanism (shell `archive_command` or an archive module via
`archive/archive_module.h`), and on success renames `.ready` → `.done`.
[from-comment] `:5-13`

## Note on filename

The task brief mentioned both `archiver.c` and `pgarch.c`; in the current
tree only `pgarch.c` exists, and it is what implements `B_ARCHIVER`
(`main_fn = PgArchiverMain` per `proctypelist.h:34`). There is no separate
`archiver.c`.

## Lifecycle

- Started by postmaster after WAL is ready for archiving (post-recovery on
  primary; not started on a standby unless `archive_mode = always`).
- Restart interval on failure: `PGARCH_RESTART_INTERVAL = 10s`.
  [from-code] `:66-67`
- Forced status-directory poll every `PGARCH_AUTOWAKE_INTERVAL = 60s`.
  [from-code] `:64-65`
- Per-file retry budget: `NUM_ARCHIVE_RETRIES = 3`. `:73`

## Key entry points (by name)

- `PgArchiverMain` — aux main loop (calls `AuxiliaryProcessMainCommon`).
- `pgarch_ArchiverCopyLoop` — drain the ready directory.
- `pgarch_archiveXlog` — invoke configured archive backend.
- `PgArchWakeup` — backend-side helper to nudge the archiver.
- `PgArchShmemSize` / `PgArchShmemInit`.

## Archive backends

- Shell: `archive/shell_archive.c` (legacy `archive_command`).
- Module: anything implementing `ArchiveModuleCallbacks` from
  `archive/archive_module.h`.

## Header

`postmaster/pgarch.h`.
