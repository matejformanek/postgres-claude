---
source_url: https://www.postgresql.org/docs/current/app-pgrewind.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_rewind — resync a diverged data directory without a full base backup

`pg_rewind` makes a data directory that diverged from another copy of the *same*
cluster consistent with that copy — the canonical use is turning a former
primary into a standby of the new primary after a failover, copying only the
*changed* blocks instead of a whole base backup. `[from-docs]`

## Core mechanism

1. **Divergence detection.** Read the target's WAL backward from the last
   checkpoint before divergence to find every data block changed on the target
   after the source's timeline forked off. `[from-docs]`
2. **Block-level copy.** Overwrite just those changed blocks with the source's
   copy. `[from-docs]`
3. **Wholesale copy.** Copy other changed/new files in full (new relfiles, WAL,
   `pg_xact`, config). Skips ephemeral dirs: `pg_dynshmem/`, `pg_notify/`,
   `pg_replslot/`, `pg_serial/`, `pg_snapshots/`, `pg_stat_tmp/`,
   `pg_subtrans/`, plus `backup_label`, `postmaster.pid`, `pgsql_tmp*`.
   `[from-docs]`
4. **Consistency setup.** Write a `backup_label` and set the minimum-consistency
   LSN in `pg_control`. `[from-docs]`
5. **WAL replay.** Normal recovery from the divergence point forward brings the
   directory to a consistent state — pg_rewind itself does not finish recovery.
   `[from-docs]`

## Hard preconditions

- **Target cleanly shut down** (else it auto-recovers in single-user mode unless
  `--no-ensure-shutdown` is given, which makes it error instead). `[from-docs]`
- **Data checksums enabled at initdb, OR `wal_log_hints=on`.** This is the
  subtle one: pg_rewind must detect *every* block changed on the target since
  divergence, **including hint-bit-only changes**. Hint-bit writes are normally
  not WAL-logged; without checksums or `wal_log_hints` they'd be invisible to
  the WAL-scan and produce silent corruption. `[from-docs]`
- **`full_page_writes=on`** (default). `[from-docs]`
- Same `initdb` origin (same system identifier) for both clusters. `[from-docs]`

## Options

| Flag | Meaning |
|---|---|
| `-D`, `--target-pgdata=dir` | **Required.** The diverged directory to rewind. |
| `--source-pgdata=dir` | Source as a filesystem path (source must be shut down). |
| `--source-server=connstr` | Source as a libpq conn to a *running* server. |
| `-R`, `--write-recovery-conf` | Write `standby.signal` + append conn settings to `postgresql.auto.conf` (requires `--source-server`). |
| `-n`, `--dry-run` | Preview; don't modify the target. |
| `-c`, `--restore-target-wal` | Use the target's `restore_command` to fetch WAL pg_rewind needs but can't find. |
| `--config-file=file` | Target config file to read `restore_command` from (with `-c`). |
| `--no-ensure-shutdown` | Error instead of auto-recovering an unclean target. |
| `-P`, `--progress` | Progress reporting. |
| `--no-sync` | Skip fsync (unsafe). |
| `--sync-method={fsync\|syncfs}` | Sync strategy. |
| `--debug` | Verbose. |

## Failure semantics

If pg_rewind fails mid-run the target directory is likely unrecoverable — take a
fresh base backup instead. After success, configure the target as a standby
(`standby.signal` / `recovery.signal` + `primary_conninfo`/`restore_command`, or
let `-R` do it). `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/app-pgchecksums.md]]` — the checksums half of the
  checksums-or-`wal_log_hints` precondition.
- `[[knowledge/docs-distilled/app-pgcontroldata.md]]` — the timeline / REDO LSN
  fields pg_rewind reasons over to find the divergence point.
- `[[knowledge/docs-distilled/wal-internals.md]]`,
  `[[knowledge/docs-distilled/logical-replication-architecture.md]]`,
  `[[knowledge/docs-distilled/runtime-config-replication.md]]` — timeline +
  standby configuration context.
- Skill: `replication-overview`, `wal-and-xlog`.
