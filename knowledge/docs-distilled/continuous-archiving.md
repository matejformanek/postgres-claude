---
source_url: https://www.postgresql.org/docs/current/continuous-archiving.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Continuous Archiving and Point-in-Time Recovery (§25.3)

The **physical** backup+recovery mechanism: a base backup (crash-fuzzy filesystem
copy) plus a continuous stream of archived WAL segments, replayed forward to any
chosen point. This is the root chapter behind the whole physical-HA family
(warm-standby, hot-standby, failover) and the developer tools already distilled
(`pg_basebackup`, `pg_verifybackup`, `pg_combinebackup`, `pg_waldump`).

## WAL archiving — enabling + the archiver

- Requires **`wal_level` ≥ `replica`** (restart), **`archive_mode = on`**
  (restart), and **exactly one of** `archive_command` (shell) or
  `archive_library` (loadable C module). [from-docs]
- `archive_command` substitutions: **`%p`** = path relative to the data dir,
  **`%f`** = bare filename. Non-zero exit ⇒ PG **keeps the segment and retries
  forever**; the segment is not recycled until archived. [from-docs]
- **The archive command MUST refuse to overwrite an existing file.** Canonical
  guard: `test ! -f /archive/%f && cp %p /archive/%f`. A blind `cp`/`rsync` that
  overwrites is a corruption hazard: PG may re-submit a segment after a crash
  before it durably recorded the prior success, so an overwrite can clobber a
  good archived file with a truncated one. [from-docs] — see idiom
  `knowledge/idioms/archive-command-fallback.md`.
- **`archive_timeout`** forces a segment switch so unarchived data can't sit
  indefinitely; forced switches still emit **full-size 16 MB segments** (archive
  bloat is the cost of a low timeout). [from-docs]
- The `.ready` / `.done` handshake lives in **`pg_wal/archive_status/`**: the
  backend marks a completed segment `.ready`, the archiver renames it `.done`
  after `archive_command` succeeds. [from-comment — named in docs; mechanism in
  `src/backend/postmaster/pgarch.c` @ anchor]
- If archiving stalls and **`pg_wal/` fills, the server PANICs** (no committed
  data lost, but the cluster is down) — monitoring archive success is
  operationally mandatory. [from-docs]

## Base backup via the low-level API

- Sequence, all in **one persisting session**: `SELECT pg_backup_start(label,
  fast => false)` → copy the data dir with any tar/cpio → `SELECT * FROM
  pg_backup_stop(wait_for_archive => true)`. If the session dies mid-backup the
  backup **auto-aborts**. [from-docs]
- `pg_backup_start(fast => false)` **waits for the next checkpoint** (spreads I/O)
  unless `fast => true`. The **redo point** established here — not the backup's
  end — is where recovery must begin. [from-docs]
- **The exclusive low-level API was removed**; only the **non-exclusive**
  `pg_backup_start`/`pg_backup_stop` pair exists (a crash no longer strands a
  stale `backup_label`). [from-docs / inferred — historical `pg_start_backup`
  gone in current tree]
- `pg_backup_stop()` returns a row: **(last required WAL file, backup_label
  contents, tablespace_map contents)**. You must write columns 2 and 3 **byte-for-
  byte, binary mode** to `backup_label` and `tablespace_map` in the copy's root.
  [from-docs]
- The **`backup_label`** carries the label, `pg_backup_start` timestamp, and the
  START WAL location; the startup process reads it to find the redo LSN and to
  refuse to treat the copy as an ordinary crashed cluster. [from-docs]
- When copying, **omit** `pg_wal/` (and its contents), postmaster.pid, and
  transient dirs; WAL is supplied separately via the archive. [from-docs]

## Incremental backups (PG17+)

- `pg_basebackup --incremental=<manifest>` stores only blocks changed since the
  reference backup, using the **WAL summaries** in `pg_wal/summaries/`
  (produced by the **WAL summarizer**, `summarize_wal = on`). [from-docs]
- Recovery from an incremental first requires **`pg_combinebackup`** to
  synthesize a full backup from base + the whole incremental chain; you cannot
  restore an incremental directly. [from-docs] — see
  `knowledge/docs-distilled/app-pgverifybackup.md`,
  `knowledge/docs-distilled/backup-manifest-format.md`.

## Recovering — targets, signal files, timelines

- Restore the base backup, drop a **`recovery.signal`** file (targeted PITR) or
  **`standby.signal`** (continuous replay), set **`restore_command`**, start. The
  startup process deletes whichever signal file it used once recovery ends.
  [from-docs]
- `restore_command` must **exit non-zero (cleanly) when the requested file is
  absent** — that's the *normal* end-of-archive signal, not an error. [from-docs]
- Recovery-target GUCs: **`recovery_target`** (`'immediate'`),
  **`recovery_target_time` / `_xid` / `_lsn` / `_name`**, plus
  **`recovery_target_inclusive`** (stop just after vs just before) and
  **`recovery_target_action`** = `pause` (default) / `promote` / `shutdown`.
  Only **one** target kind may be set. [from-docs]
- **WAL is sought archive-first** (`restore_command`), then `pg_wal/` — the
  validated archive copy is preferred over any leftover local segment. [from-docs]
- **Timelines:** every recovery/promotion forks a **new timeline** (the hex
  prefix in a segment name, e.g. `00000002...`) and writes a
  **`<TLI>.history`** file. This lets PITR reach even *abandoned* branches.
  `recovery_target_timeline` defaults to **`latest`**; set `current` or a
  specific TLI to follow a chosen branch. You cannot target a timeline that
  branched **before** the base backup. [from-docs] — see idiom
  `knowledge/idioms/xlog-region-replay.md`.

## Caveats

- A base backup is **NOT** filesystem-consistent on its own — replaying the WAL
  from the redo point is what repairs the internal fuzziness. [from-docs]
- **`CREATE TABLESPACE` is WAL-logged with absolute paths** and replayed as-is;
  restoring on the same host can overwrite the live tablespace. Take a fresh base
  backup after any tablespace change. [from-docs]
- Old WAL segments become deletable only once a **newer** base backup no longer
  needs them (the `.backup` history file records the exact required range).
  [from-docs]

## Links into corpus

- `knowledge/docs-distilled/backup-file.md` — the "just cp the data dir" pitfall
  this chapter is the answer to.
- `knowledge/docs-distilled/warm-standby.md` — same `restore_command` +
  `standby.signal` machinery run continuously instead of to a target.
- `knowledge/docs-distilled/app-pgbasebackup.md`,
  `.../app-pgverifybackup.md`, `.../app-pgcontroldata.md` — the tools that
  wrap / verify / inspect this flow.
- `knowledge/docs-distilled/wal-reliability.md`,
  `.../wal-configuration.md`, `.../runtime-config-wal.md` — the WAL durability
  layer underneath.
- `knowledge/idioms/archive-command-fallback.md`,
  `.../crash-recovery-startup.md`, `.../checkpoint-coordination.md`,
  `.../xlog-region-replay.md` — the code paths.
- `knowledge/subsystems/access-transam.md`,
  `knowledge/subsystems/replication.md`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/continuous-archiving.html (PG18).
- Mechanism names flagged `[from-comment]` (`pg_wal/archive_status/` `.ready`/
  `.done`, WAL summarizer) are doc-referenced; the C is in
  `source/src/backend/postmaster/pgarch.c` and
  `source/src/backend/postmaster/walsummarizer.c` at anchor `a5422fe3bd7e` —
  not line-verified this run.
