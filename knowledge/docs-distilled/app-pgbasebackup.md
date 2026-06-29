---
source_url: https://www.postgresql.org/docs/current/app-pgbasebackup.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: streaming-replication-clients (2026-06-29 refill)
---

# pg_basebackup — physical base backup over the replication protocol

`pg_basebackup` takes a binary base backup of a *running* cluster by issuing the
`BASE_BACKUP` replication command to a walsender over a libpq connection. It is
the standard way to seed a standby or take a PITR base image. `[from-docs]`

## Non-obvious claims

- **Needs a replication connection + a REPLICATION-privileged role**, and
  `pg_hba.conf` must permit replication. With `-X stream` (default) it opens
  **two** connections — one for data, one to stream WAL concurrently — so
  `max_wal_senders` must allow ≥ 2. `[from-docs]`
- **`-X stream` is the default for a consistency reason:** streaming the WAL
  generated *during* the backup makes the output self-contained and immediately
  startable without consulting the WAL archive. `-X fetch` collects WAL only at
  the end (needs server-side `wal_keep_size`/retention); `-X none` omits it,
  leaving an incomplete backup. `[from-docs]`
- **`-c fast` vs `-c spread`.** The backup begins with a checkpoint; `fast`
  forces it immediately (quicker start, I/O spike), `spread` (default) spreads
  it over `checkpoint_timeout`. `[from-docs]`
- **Compression can be client- or server-side.** `-Z server-gzip:level=9`,
  `-Z client-lz4`, `-Z zstd:level=3,workers=4`. Server compression cuts
  bandwidth at the cost of server CPU; it does **not** apply to WAL under
  `-X stream` (compress WAL client-side or use `-X fetch`). `[from-docs]`
- **`--target=server:/path` / `blackhole` can't combine with `-X stream`** (use
  `-X fetch`/`none`); `server` needs superuser or `pg_write_server_files`.
  `[from-docs]`
- **`-R`/`--write-recovery-conf` writes `standby.signal` + `primary_conninfo`
  (and slot) into `postgresql.auto.conf`** — the one-flag standby bootstrap.
  `[from-docs]`
- **Incremental backups (`-i`/`--incremental=OLD_MANIFEST`, server v17+)** record
  only changed blocks vs a prior manifest and must be reassembled with
  `pg_combinebackup` before use. `[from-docs]`

## Manifest options (feed pg_verifybackup)

`--manifest-checksums={NONE|CRC32C|SHA224..512}` (default CRC32C — fast; SHA* for
crypto verification), `--no-manifest`, `--manifest-force-encode` (hex-encode all
names). The manifest lists every non-WAL file with size/mtime/checksum and ends
with its own SHA256 — consumed by `pg_verifybackup`. `[from-docs]`

## Other key flags

`-D dir` (required), `-F plain|tar`, `-S slot` / `-C`/`--create-slot` /
`--no-slot`, `-T olddir=newdir` (tablespace remap, plain only), `-r`/`--max-rate`
(throttle 32 KB/s–1024 MB/s), `-P`/`--progress` (via
`pg_stat_progress_basebackup`), `-l`/`--label`, `--waldir`, `--sync-method`,
`--no-verify-checksums`, `-N`/`--no-sync`. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/app-pgverifybackup.md]]`,
  `[[knowledge/docs-distilled/backup-manifest-format.md]]` — the manifest this
  produces and the tool that verifies it.
- `[[knowledge/docs-distilled/protocol-replication.md]]` — the `BASE_BACKUP` /
  replication-protocol commands underneath.
- `[[knowledge/docs-distilled/app-pgreceivewal.md]]` — the WAL-only sibling that
  uses the same walsender path.
- `[[knowledge/docs-distilled/app-pgrewind.md]]` — the alternative to a full
  base backup when re-syncing a diverged former primary.
- Skill: `replication-overview`, `wal-and-xlog`.
