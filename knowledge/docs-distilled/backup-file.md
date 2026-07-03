---
source_url: https://www.postgresql.org/docs/current/backup-file.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# File System Level Backup (§25.2)

The short chapter that exists to say **"cp -r the data dir of a running server
does NOT work"** — and to carve out the one exception (a truly atomic filesystem
snapshot). It's the naive alternative that `continuous-archiving.md` and
`pg_basebackup` are the correct answers to.

## Why a raw copy of a running cluster is invalid

- `tar`/`cp` is **not atomic**: files change under you mid-copy, so the copy is
  internally torn — and freezing client connections does **not** help, because
  PG's own **shared-buffer contents haven't been flushed to disk**. [from-docs]
- **The server must be shut down** for a valid plain file-system copy. This is
  non-negotiable for a raw `tar`/`cp`. [from-docs]
- Individual table/database files are **not usable in isolation** — a table's
  file is meaningless without **`pg_xact/`** (commit-status SLRU) and the rest of
  the cluster's shared state. Backup and restore are **all-or-nothing for the
  entire cluster**; you cannot cp out one database's files and restore just those.
  [from-docs] — see idiom `knowledge/idioms/clog-slru.md`,
  `knowledge/docs-distilled/storage-file-layout.md`.

## The atomic-snapshot exception

- A **truly atomic** volume snapshot of a *running* server **is** usable: it
  captures the state as a **crash-at-the-instant**, and WAL replay on next start
  repairs the fuzziness — no server shutdown needed. [from-docs]
- The catch: the snapshot must be atomic **across every filesystem involved
  simultaneously** — data dir **and** a separately-mounted `pg_wal/` **and** every
  tablespace. Independent per-volume snapshots taken at slightly different instants
  are inconsistent and may be unrecoverable. [from-docs]
- If you can't get one simultaneous multi-volume snapshot, use the **low-level
  `pg_backup_start`/`pg_backup_stop` API** (or `pg_basebackup`), which is immune
  to files changing during the copy because the backup boundary is WAL-defined,
  not wall-clock-defined. [from-docs]

## Practical notes

- **rsync two-pass** to shrink downtime: rsync once with the server up, then stop
  it and rsync again with **`--checksum`** — the second pass needs checksums
  because rsync's mtime granularity is only **1 second** and would miss
  sub-second changes. [from-docs]
- File-system backups are usually **larger** than `pg_dump` output (a dump omits
  index data, storing only the DDL to rebuild) but can be **faster** to take/
  restore. Different category from logical dumps entirely. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/continuous-archiving.md` — the correct online-backup
  answer (base backup + WAL replay) this chapter defers to.
- `knowledge/docs-distilled/app-pgbasebackup.md` — the tool that does the
  low-level API for you.
- `knowledge/docs-distilled/storage-file-layout.md` — what's actually in the data
  dir (`pg_xact/`, `pg_wal/`, `base/`, `pg_tblspc/`).
- `knowledge/idioms/clog-slru.md`, `.../crash-recovery-startup.md`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/backup-file.html (PG18).
