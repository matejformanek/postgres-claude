---
name: backup-and-recovery
description: PostgreSQL's backup + point-in-time recovery — `pg_basebackup` + WAL archiving (archive_command / archive_library) + `restore_command` + `pg_wal_replay_*` targets + the pg_backup_start/stop API + `pg_receivewal`. Covers `src/backend/backup/` (basebackup server code) + `src/backend/postmaster/pgarch.c` (archiver aux process) + `src/backend/access/transam/xlogrecovery.c` (recovery driver). Loads when the user asks about how base backups work, WAL archiving vs streaming replication, PITR targets (`recovery_target_*`), `pg_backup_start`/`pg_backup_stop` low-level API, `.backup` files, restore_command semantics, or incremental backup (PG 17+ with `WAL_SUMMARIZED`). Skip when the ask is about `pg_dump` (logical dump — different tool) or about physical replication streaming (`physical-replication` — related but sibling).
when_to_load: Design or debug a backup strategy; touch base-backup server code; understand PITR targets; work with WAL archiving; add a new recovery target type; extend pg_backup_start/stop.
companion_skills:
  - physical-replication
  - wal-and-xlog
  - process-lifecycle
---

# backup-and-recovery — base backup + WAL archiving + PITR

PG's backup strategy is TWO PARTS:

1. **Base backup** — a full copy of the data directory at a point in time. Made by `pg_basebackup` (client) which drives the server's basebackup code, OR by filesystem-level tools + `pg_backup_start` / `pg_backup_stop`.
2. **WAL archive** — every WAL segment shipped to secondary storage as it fills. Enables replay from the base backup to any later LSN.

Together: recovery starts from base backup + replays WAL up to the desired point (crash-recovery-latest, specific LSN, specific time, specific named restore point).

## The file map

### Backup (primary side)

| File | Role |
|---|---|
| `src/backend/backup/basebackup.c` | Server-side base-backup driver — walks the data directory, streams files to client, coordinates checkpoint. |
| `src/backend/backup/basebackup_copy.c` | Copy protocol integration. |
| `src/backend/backup/basebackup_gzip.c` / `_lz4.c` / `_zstd.c` | On-the-fly compression variants. |
| `src/backend/backup/basebackup_target.c` | Where to write — client stream vs server-side path. |
| `src/backend/backup/basebackup_incremental.c` | (PG 17+) Incremental backup driver — uses WAL summary files. |
| `src/backend/backup/basebackup_progress.c` | Progress reporting via pgstat_progress_backup. |
| `src/backend/backup/basebackup_server.c` | Server-side backup target — writes to a filesystem path directly, not client-stream. |
| `src/backend/postmaster/pgarch.c` | The archiver aux process — invokes `archive_command` / `archive_library` per WAL segment. |
| `src/backend/postmaster/walsummarizer.c` | (PG 17+) WAL summarizer — produces `.summary` files for incremental backup. |

### Recovery (standby / restore side)

| File | Role |
|---|---|
| `src/backend/access/transam/xlogrecovery.c` | The recovery driver — StartupXLOG. Runs at both crash recovery and PITR. |
| `src/backend/access/transam/xlogrecovery.c` recovery_target dispatch | Handles `_time` / `_xid` / `_lsn` / `_name` / `_immediate` targets. |
| `src/backend/access/transam/xlogreader.c` | Reading WAL records back — used by recovery + by pg_waldump. |
| `src/bin/pg_basebackup/pg_basebackup.c` | Client-side pg_basebackup tool. |
| `src/bin/pg_basebackup/pg_receivewal.c` | Streaming WAL to files continuously. |
| `src/bin/pg_basebackup/pg_createsubscriber.c` | (PG 17+) Convert a physical standby to a logical subscriber. |

## The base-backup flow

`pg_basebackup -D destination -X stream` runs this sequence:

1. Client opens a **replication connection** (same protocol as walsender).
2. Sends `BASE_BACKUP` command.
3. Server: `SendBaseBackup` starts:
   - `RequestXLogSwitch` — get a fresh WAL boundary.
   - `pg_backup_start` — record the START LSN, produce the backup label.
   - Iterate data directory files, streaming each to client.
   - `pg_backup_stop` — record the STOP LSN.
4. Client: writes files to destination, then requests WAL from START to STOP (via streaming with the walsender or separately).
5. Result: consistent base backup at the STOP LSN.

The "consistent" part is subtle: the backup files are copied WHILE writes may be happening. Consistency comes from replaying the WAL from START to at least STOP — reaching a "backup end record" that guarantees recovery has caught up.

## The archive flow

When `archive_mode = on`:

1. `pgarch.c` waits for a WAL segment to be marked complete.
2. Invokes `archive_command` (shell string) OR `archive_library` (a loaded C library).
3. Command/library copies the WAL segment to the archive location (S3, NFS, etc.).
4. On success, `pgarch.c` marks the segment archived (via a `.ready` → `.done` rename in `pg_wal/archive_status/`).
5. Segment can now be recycled by the checkpointer.

`archive_library` (PG 15+) is the modern path — no shell dependency, no per-file fork() cost.

## The restore flow

`postgresql.auto.conf` or a manual recovery config sets:

- `restore_command` — shell command to fetch a WAL segment.
- `recovery_target_*` — where to stop.

On startup with a `standby.signal` OR `recovery.signal` file present:

1. Startup process reads the backup_label to find START LSN.
2. Invokes `restore_command` for the WAL segments.
3. `xlogrecovery.c` replays each record.
4. At each record: check if recovery target reached. If yes, stop.
5. Cleanup, promote if appropriate.

## Recovery targets

Set via `postgresql.conf`:

- `recovery_target = 'immediate'` — stop at consistency point (end of base-backup WAL).
- `recovery_target_time = '2026-07-07 14:00:00'` — stop when a commit's timestamp exceeds this.
- `recovery_target_xid = 12345` — stop after this XID commits.
- `recovery_target_lsn = '0/12345678'` — stop at LSN.
- `recovery_target_name = 'my_restore_point'` — stop at a named restore point created by `pg_create_restore_point`.

`recovery_target_inclusive` — stop AT the target vs one before.
`recovery_target_action` — pause / promote / shutdown when target reached.
`recovery_target_timeline` — which timeline to follow after a promotion history.

## Timelines

Each promotion of a standby creates a new **timeline** — a fork of history from the promotion LSN. Files in `pg_wal/`:

- `000000010000000000000001` — timeline 1's segment 1.
- `000000020000000000000042` — timeline 2's segment 42 (timeline 2 branches from ~LSN 0/42000000).

`pg_wal/00000002.history` — describes the branch point.

Recovery can follow a specific timeline via `recovery_target_timeline`. Default: latest.

## Incremental backup (PG 17+)

New in PG 17: `pg_basebackup --incremental=<prev_backup_manifest>` reads the previous backup's manifest + WAL summaries from `pg_wal/summaries/` and only streams changed blocks.

Requires `wal_level >= 'replica'` (default) + `summarize_wal = on`.

Restore: `pg_combinebackup` merges incrementals into a full backup usable for recovery.

## Common patch shapes

### Add a new recovery target

- Extend `recovery_target*` GUC set in guc_tables.c.
- Parse into RecoveryTargetType enum.
- `xlogrecovery.c` per-record: extend the target-reached check.
- Docs.

### Add a new base-backup format / compression

- Basebackup_<name>.c — implement the streaming interface (`BbSink` API).
- Wire into basebackup.c dispatch.
- pg_basebackup client-side --compress option support.

### Debug "restore_command not running"

- Check `postgresql.auto.conf` and postgresql.conf for the setting.
- Check for `recovery.signal` OR `standby.signal` in data dir — required for recovery mode.
- Look at server log — `restore_command` failures are logged.
- Test manually: `restore_command` should return 0 and place the file at `%p`.

### Extend `pg_backup_start` API

- Rare — the low-level API is stable.
- Would touch xlog.c backup_start_time bookkeeping.

## Pitfalls

- **`archive_command` failures block WAL recycling** — a failing archive command causes `pg_wal/` to grow indefinitely. Monitor `pg_stat_archiver.failed_count`.
- **Base backup can take much longer than expected** — a 1TB database with default compression takes ~2h; with `--compress=server-lz4` or `--compress=zstd` it's usually faster.
- **The backup_label file must NOT be deleted from the data directory** — the recovery uses it to find the correct starting LSN.
- **Recovery is single-threaded** — the startup process replays WAL sequentially. Parallel replay was proposed but not yet in master.
- **Timeline switch semantics are subtle** — if you promote a standby, that becomes a new timeline. Subsequent WAL from the OLD timeline is orphaned unless you replay it before the promotion LSN.
- **`recovery_target_action = 'pause'`** leaves the standby paused after reaching the target. Manual `pg_wal_replay_resume` needed to continue.
- **`pg_basebackup -X stream` doesn't include WAL from BEFORE the base backup** — for PITR you need archived WAL from BEFORE the STOP LSN to reach older restore targets.
- **archive_library vs archive_command precedence** — you can only set ONE. Setting both is an error.
- **File-system level backups + tar** — remember to include `pg_wal/` OR ensure archived WAL is available.
- **`pg_basebackup --no-slot` vs `--slot`** — with slot, the primary keeps WAL until the slot is dropped. Great for reliability, dangerous if the client dies mid-backup.
- **Incremental backup requires the SAME base for all incrementals in a chain** — you can't mix incrementals from different bases.
- **`recovery_end_command`** — misconfigured, can cause promotion issues.

## Related corpus

- **Idiom**: `archive-command-fallback`, `crash-recovery-startup`.
- **Subsystems**: `access-transam` (WAL machinery, xlog.c), `replication` (walsender used by pg_basebackup and pg_receivewal).
- **Related skills**: `physical-replication` (streaming rep uses the same replication protocol), `wal-and-xlog` (WAL insertion side).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom crash-recovery-startup
python3 scripts/corpus-chain.py --file src/backend/backup/basebackup.c
python3 scripts/corpus-chain.py --file src/backend/access/transam/xlogrecovery.c
```

## Boundary

**Use this skill** for base-backup + WAL archiving + PITR + restore_command + incremental backup.

**Don't use** for:
- **`pg_dump`** — logical dump, different tool. Uses SQL layer, not WAL.
- **Physical streaming replication** — sibling; see `physical-replication`.
- **WAL writing on the primary** — that's the WAL infrastructure, see `wal-and-xlog`.
- **Logical replication** — completely different system.
- **`pg_upgrade`** — major-version upgrades, different mechanism.
- **`pg_repack` / online reorganization** — third-party tools.
