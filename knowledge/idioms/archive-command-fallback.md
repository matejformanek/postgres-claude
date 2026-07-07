# Archive command fallback — pgarch + archive_command + archive_library

PostgreSQL ships WAL segments to a backup location via the
**archiver process** (`pgarch.c`). The archiver supports two
interfaces: the legacy `archive_command` (a shell command
template) and the modern `archive_library` (a loadable C
module). The legacy path remains the default for most
installations; the library path is the one new development
targets. A cluster can configure EXACTLY ONE — not both.

Anchors:
- `source/src/backend/postmaster/pgarch.c` — archiver process
  [verified-by-code]
- `source/src/backend/postmaster/pgarch.c:884-885` — the
  "both set is error" check [verified-by-code]
- `knowledge/subsystems/contrib-basic_archive.md` — the
  reference archive_library implementation
- `knowledge/subsystems/replication.md` — surrounding system

## The archiver process

`pgarch_main()` is the archiver's main loop. The process is:

1. Started by postmaster when `archive_mode = on`.
2. Watches `pg_wal/archive_status/` for `.ready` flag files.
3. For each ready segment, invokes the configured archive
   interface.
4. On success, renames `.ready` → `.done`.
5. On failure, sleeps + retries.

One archiver process per cluster; serial archiving (one
segment at a time).

## archive_command — the shell template

```ini
archive_command = 'test ! -f /backup/%f && cp %p /backup/%f'
```

Template variables:
- **`%p`** — full path to the WAL segment in `pg_wal/`.
- **`%f`** — just the filename (16-char hex segment name).
- **`%r`** — last-checkpoint redo position.

The archiver forks a shell, expands the template, and runs
it. Exit code 0 = success; non-zero = failure (retry).

[verified-by-code `pgarch.c:520` `pgarch_archiveXlog`]

## The classic archive_command pitfalls

[from the `basic_archive.md` companion doc]

- **Per-segment fork** is expensive on busy clusters.
- **No fsync** unless explicitly added to the template.
- **Race conditions** on the existence-check + copy.
- **Quoting hazards** on filenames containing special chars
  (though WAL filenames are hex, so this is theoretical).

The template's `test ! -f` check exists to prevent
re-archive-after-crash from failing — without it, a crash
between successful copy and PG recording success makes the
next start re-archive AND fail because the file exists.

## archive_library — the modern interface

```ini
archive_library = 'basic_archive'
basic_archive.archive_directory = '/backup'
```

The library is loaded into the archiver process at startup.
It exports `ArchiveModuleCallbacks` (see
`contrib-basic_archive.md`). The callbacks run in-process,
no fork.

Benefits:
- **No fork per segment** — function call.
- **Per-archive state** — caller can maintain connection
  pools, auth tokens.
- **Direct fsync** — no shell-quoting concerns.
- **Better error reporting** — callbacks can return
  structured errors.

## The mutual-exclusion check

[verified-by-code `pgarch.c:884-885`]

```c
errmsg("both \"archive_command\" and \"archive_library\" set"),
errdetail("Only one of \"archive_command\", \"archive_library\" may be set.")));
```

A cluster with both `archive_command` and `archive_library`
set is rejected at startup. The check is in pgarch.c, not
GUC validation, because the mutual exclusion depends on
non-empty values (empty is allowed for both = no archiving).

## The retry policy

Failed archives sleep before retry:

- First attempt: immediate.
- Second attempt: 1 second.
- Subsequent: exponential backoff up to ~60 seconds.

No upper bound on retries — pg_wal grows until the
underlying issue is fixed. There's no auto-give-up.

`archive_timeout` (different from retry) is the
"force a WAL switch every N seconds" GUC — useful for
ensuring archives happen even on idle systems.

## The WAL retention link

WAL segments not yet `.done` are retained in `pg_wal/`. A
failing archive (network down, backup disk full) prevents
WAL removal. The disk grows until either:
- The archive succeeds (catch-up).
- The cluster is manually intervened (clear pg_wal, accept
  the gap).

This is the "stuck archiver" disk-bloat case. Monitor with:

```sql
SELECT last_archived_wal, last_archived_time
FROM pg_stat_archiver;
```

If `last_archived_time` is hours ago, the archiver is
stuck.

## Migration: archive_command → archive_library

For new clusters, prefer `archive_library`. For migration:

1. Build / install the library module.
2. Set `archive_library = 'basic_archive'` (or your
   library).
3. Configure library-specific options.
4. Reload PG configuration.
5. Confirm `pg_stat_archiver` continues to show successful
   archives.
6. UNSET `archive_command`.

The reload accepts the new library; existing in-flight
archives finish using the OLD setting; subsequent archives
use the new.

## Common review-time concerns

- **Don't write your own archive_command shell template
  without `fsync`** — torn writes on power loss = corrupt
  backup.
- **archive_library callbacks must be crash-safe** — same
  fsync + atomic-rename pattern as basic_archive.
- **Both unset = no archiving** — `archive_mode = on` is
  necessary but not sufficient.
- **Test the archive before relying on it** — `pg_basebackup
  --wal-method=stream` for a one-off test.
- **Library and command are mutually exclusive**; don't try
  to "use both."

## Invariants

- **[INV-1]** archive_command and archive_library are
  mutually exclusive.
- **[INV-2]** Per-segment retry has exponential backoff;
  no upper bound on retries.
- **[INV-3]** Failed archive blocks WAL removal; disk grows.
- **[INV-4]** archive_library runs in-process; no fork
  per segment.
- **[INV-5]** `.ready` → `.done` is the atomic success
  marker per WAL segment.

## Useful greps

- The mutual-exclusion check:
  `grep -n 'archive_command.*archive_library' source/src/backend/postmaster/pgarch.c`
- The retry loop:
  `grep -n 'pgarch_archiveXlog\|HandlePgArchInterrupts' source/src/backend/postmaster/pgarch.c | head -10`
- The archive_library load:
  `grep -RIn 'LoadArchiveLibrary\|_PG_archive_module_init' source/src/backend`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/postmaster/pgarch.c`](../files/src/backend/postmaster/pgarch.c.md) | 884 | the "both set is error" check |
| [`src/backend/postmaster/pgarch.c`](../files/src/backend/postmaster/pgarch.c.md) | — | archiver process |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/subsystems/contrib-basic_archive.md` — reference
  archive_library implementation.
- `knowledge/idioms/replication-slot-advance.md` — replication
  slots vs WAL archiving (different retention mechanisms).
- `knowledge/idioms/wal-record-construction.md` — what's IN a
  WAL segment.
- `knowledge/subsystems/replication.md` — replication +
  archive subsystems.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL skill.
- `source/src/backend/postmaster/pgarch.c` — archiver
  process.
