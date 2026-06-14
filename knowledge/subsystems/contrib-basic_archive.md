# contrib-basic_archive (WAL archive module template)

- **Source path:** `source/contrib/basic_archive/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `archive_library` GUC (NOT `shared_preload_libraries`)
- **Surface:** zero SQL functions; one GUC; one archive-module
  registration

## 1. Purpose

Reference implementation of the **archive_library** interface
introduced in PG 15. Provides the in-tree minimal alternative to
the legacy shell-command-based `archive_command`. Demonstrates
the canonical "copy WAL segment to a destination directory with
crash-safe atomicity" pattern that production archive libraries
(pgbackrest, barman, wal-g) follow.

Roughly equivalent to:
```bash
test ! -f /path/to/dest && cp /path/to/src /path/to/dest
```

[from-comment `basic_archive.c:6-7`]

But with crucial differences: writes to a temp file first, fsyncs,
then durably renames. And if the destination already exists with
identical content, the archive succeeds (idempotency for the
crash-recovery case where archive succeeded but PG didn't record
it).

## 2. The archive_library interface

[verified-by-code `basic_archive.c:50-56`]

```c
static const ArchiveModuleCallbacks basic_archive_callbacks = {
    .startup_cb           = NULL,
    .check_configured_cb  = basic_archive_configured,
    .archive_file_cb      = basic_archive_file,
    .shutdown_cb          = NULL,
};

const ArchiveModuleCallbacks *
_PG_archive_module_init(void)
{
    return &basic_archive_callbacks;
}
```

The four callbacks (all optional except `archive_file_cb`):

| Callback | When called |
|---|---|
| `startup_cb` | Once at archiver process start; init per-archive state |
| `check_configured_cb` | Before each archive attempt; verify config is valid |
| `archive_file_cb` | Per WAL segment; do the actual copy |
| `shutdown_cb` | At archiver process exit; cleanup |

basic_archive uses only `check_configured` and `archive_file`.
A more sophisticated module (encrypting, compressing, uploading
to S3) would use all four.

## 3. The single GUC

`basic_archive.archive_directory` — string, the destination path
for archived WAL segments. Empty means "not configured" — the
`check_configured_cb` returns false until the GUC is set.

## 4. The crash-safe copy

`basic_archive_file()` performs the canonical durable-write
pattern:

1. Check if destination already exists.
2. If exists and contents identical → return success
   (idempotency for re-archive-after-crash case).
3. Build a temp filename in the destination directory.
4. Open temp, write the source contents, `fsync`.
5. Rename temp → final name (atomic on POSIX).
6. `fsync` the destination directory (so the rename is durable).

The "compare contents on existence" is the key idempotency
mechanism. PG's archiver may have completed the copy but crashed
before recording success in the control file; on restart, the
same file gets re-archived. Without the idempotency check, the
re-archive would fail with "file exists" and PG would never know
the original archive succeeded.

## 5. The two pre-check phases

[verified-by-code `basic_archive.c:54-55`]

- **`basic_archive_configured`** — fires before each archive
  attempt. Returns false if `archive_directory` GUC is empty.
  When false, the archiver process sleeps and retries; the WAL
  segment stays in `pg_wal/`.
- **`basic_archive_file`** — the actual copy. Returns true on
  success, false on failure. PG retries on failure with
  exponential backoff.

## 6. The "why not shell?" argument

The legacy `archive_command` was:

```ini
archive_command = 'test ! -f /backup/%f && cp %p /backup/%f'
```

Problems with shell:

- **Forking is expensive** for every WAL segment.
- **No fsync** unless explicitly added.
- **Race conditions** on the existence-check + copy.
- **No per-archive state** for connection pooling or auth tokens.
- **Quoting hazards** on filenames with special chars.

archive_library solves all of these by running in-process:

- No fork per segment.
- Direct file syscalls + fsync.
- No quoting issues.
- State can persist across archive attempts.

The legacy `archive_command` still works (and most installations
still use it), but new archive backends use the library interface.

## 7. The archiver process

PG's archiver is a separate process (one per cluster) that:

1. Watches `pg_wal/archive_status/` for `.ready` flag files.
2. Per ready segment, calls the archive_library's
   `archive_file_cb`.
3. On success, renames the flag from `.ready` to `.done`.
4. On failure, sleeps and retries.

basic_archive is loaded into the archiver process at startup;
its callbacks run there, not in user backends.

## 8. Production-use guidance

- **DO NOT use basic_archive in production.** It's intentionally
  minimal. Use pgbackrest, barman, or wal-g for real
  point-in-time-recovery (PITR) infrastructure.
- **It IS useful for:** quick local testing of PITR setups,
  understanding the archive_library API, building custom
  archive backends.
- **Set `archive_mode = on`** in postgresql.conf to enable the
  archiver process.
- **Set `archive_library = 'basic_archive'`** to use the
  library instead of `archive_command`.
- **Set `basic_archive.archive_directory = '/path/to/backup'`**.

## 9. Invariants

- **[INV-1]** `archive_file_cb` MUST be crash-safe — partial
  writes / non-atomic renames break PITR.
- **[INV-2]** Idempotent on retry — re-archive must succeed if
  destination is identical.
- **[INV-3]** No SQL surface; activation via `archive_library`
  GUC.
- **[INV-4]** Runs in the archiver process, not user backends.
- **[INV-5]** Returning false from `archive_file_cb` triggers
  retry with backoff; segment stays in `pg_wal/`.

## 10. Useful greps

- The callback registration:
  `grep -n 'ArchiveModuleCallbacks\|_PG_archive_module_init' source/contrib/basic_archive/basic_archive.c`
- The archive API in core:
  `grep -n 'archive_module\|ArchiveModuleCallbacks' source/src/include/archive/archive_module.h`
- The archiver process:
  `grep -RIn 'PgArchiverMain' source/src/backend/postmaster | head -10`

## 11. Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  archive_library loading is distinct from shared_preload_libraries.
- `.claude/skills/wal-and-xlog/SKILL.md` — archive_mode + WAL
  segment lifecycle.
- `knowledge/subsystems/replication.md` — archive is one of the
  three WAL-shipping paths.
- `knowledge/idioms/wal-record-construction.md` — what's IN a
  WAL segment that gets archived.
- `source/src/include/archive/archive_module.h` — the public API.
- `source/src/backend/postmaster/pgarch.c` — the archiver
  process implementation.
- `source/contrib/basic_archive/basic_archive.c` — the
  reference implementation.
