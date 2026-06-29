---
source_url: https://www.postgresql.org/docs/current/app-pgchecksums.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_checksums — enable / disable / verify data-page checksums offline

`pg_checksums` toggles or verifies per-data-page checksums on an **offline**
cluster, working at the file level on relation files plus `pg_control`. Default
mode is verify-only. `[from-docs]`

## Non-obvious claims

- **Cluster-must-be-cleanly-shut-down invariant.** It reads `pg_control` and
  refuses to operate on a running or uncleanly-shut-down cluster. This mirrors
  `pg_rewind`'s precondition — both touch raw blocks and cannot tolerate a
  concurrent writer. `[from-docs]`
- **Enable is O(cluster size); disable is O(1).** `-e` must scan every block,
  compute the checksum, rewrite the block in place, then bump
  `data_checksum_version` in `pg_control`. `-d` only edits `pg_control`.
  `[from-docs]`
- **Interrupt-safe.** If killed mid-enable/disable, the cluster's checksum state
  is left unchanged (the `pg_control` flip is the commit point); re-running
  completes it. `[from-docs]`
- **Replication footgun.** With block-copy tools (`pg_rewind`, low-level
  basebackup), enabling/disabling checksums inconsistently across primary and
  standby causes page corruption. Apply the operation to all nodes consistently
  while all are stopped, or rebuild standbys. `[from-docs]`
- **`-N`/`--no-sync` skips the final fsync** — faster, unsafe, test-only.
  `[from-docs]`

## Modes & options

| Flag | Meaning |
|---|---|
| `-c`, `--check` | **Default.** Verify every file's checksums; exit 0 if clean, nonzero on any mismatch. |
| `-e`, `--enable` | Rewrite all blocks with computed checksums, then set `data_checksum_version`. |
| `-d`, `--disable` | Clear `data_checksum_version` only (no block rewrites). |
| `-f`, `--filenode=N` | Restrict check to a single relfilenode. |
| `-N`, `--no-sync` | Skip fsync (unsafe). |
| `-P`, `--progress` | Progress reporting. |
| `-v`, `--verbose` | List every file checked. |
| `-D`, `--pgdata=dir` | Data directory (or `$PGDATA`). |
| `--sync-method={fsync\|syncfs}` | Final-sync strategy. |

## The `data_checksum_version` field

The single source of truth is `pg_control`'s `Data page checksum version`
(0 = off): set by `initdb -k` at cluster creation, flipped by
`pg_checksums -e`/`-d` offline, and read by the backend at startup to decide
whether to verify checksums on every page read. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/app-pgcontroldata.md]]` — exposes the
  `Data page checksum version` field this tool writes.
- `[[knowledge/docs-distilled/storage-page-layout.md]]` — where the per-page
  checksum lives in `PageHeaderData` (`pd_checksum`).
- `[[knowledge/docs-distilled/app-pgrewind.md]]` — shares the
  checksums-or-`wal_log_hints` block-tracking concern.
- `[[knowledge/subsystems/storage-buffer.md]]` — checksum compute/verify on
  read/flush in the buffer manager.
- Skill: `wal-and-xlog`, `debugging`.
