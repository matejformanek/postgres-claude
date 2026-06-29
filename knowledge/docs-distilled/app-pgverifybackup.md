---
source_url: https://www.postgresql.org/docs/current/app-pgverifybackup.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_verifybackup — verify a base backup against its backup_manifest

`pg_verifybackup` checks a `pg_basebackup` output against the `backup_manifest`
the server emitted during the backup. It is the read side of the §65
`backup_manifest` format. `[from-docs]`

## What it checks (four stages)

1. **Manifest validation** — parse `backup_manifest`, verify the manifest's own
   trailing SHA256, and confirm its system identifier matches `pg_control`.
2. **Presence + size** — every manifest-listed file is present at the right
   size. By design it *ignores*: `postgresql.auto.conf`, `standby.signal`,
   `recovery.signal`, the `backup_manifest` itself, and the contents of
   `pg_wal/`; only file (not directory) presence is checked.
3. **Checksums** — recompute each file's SHA256 and compare to the manifest;
   skipped for files that already failed stage 2.
4. **WAL verification** — shell out to `pg_waldump` over the WAL range the
   manifest records as required for recovery. Plain-format only — **tar-format
   backups must use `-n`/`--no-parse-wal`**. `[from-docs]`

## Cheap vs expensive

- **Cheap, always:** manifest structural integrity + presence/size.
- **Expensive, skippable:** per-file SHA256 recompute (`-s`/`--skip-checksums`
  still verifies presence+size) and WAL parse (`-n`/`--no-parse-wal`).
  `[from-docs]`

## Options

| Flag | Meaning |
|---|---|
| `-e`, `--exit-on-error` | Stop at first error (default: report all). |
| `-i`, `--ignore=path` | Skip a path; repeatable. |
| `-m`, `--manifest-path=path` | Manifest from a custom location (not backup root). |
| `-n`, `--no-parse-wal` | Skip the pg_waldump WAL-verification stage (required for tar format). |
| `-s`, `--skip-checksums` | Skip SHA256 recompute; still check presence + size. |
| `-w`, `--wal-directory=path` | Parse WAL from an alternate dir instead of `pg_wal`. |
| `-P`, `--progress` | Progress (incompatible with `-q`). |
| `-q`, `--quiet` | No output on success. |
| `target_directory` (positional) | The backup to verify. |

## Limitations

Not comprehensive — it cannot catch every issue a running server would (e.g. a
server bug that wrote valid checksums over nonsensical data); the verifying
`pg_verifybackup` version must match the server that took the backup; extra WAL
not required for recovery is not checked; real restore tests are still advised.
`[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/backup-manifest-format.md]]` — the JSON manifest
  (per-file path/size/last-modified/checksum + WAL-ranges) this tool consumes.
- `[[knowledge/docs-distilled/pgwaldump.md]]` — stage 4 invokes exactly this to
  validate the required WAL range.
- `[[knowledge/docs-distilled/app-pgcontroldata.md]]` — the system identifier
  the manifest is matched against.
- Skill: `wal-and-xlog`, `replication-overview`.
