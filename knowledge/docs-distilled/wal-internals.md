---
source_url: https://www.postgresql.org/docs/current/wal-internals.html
fetched_at: 2026-06-08T21:07:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — WAL Internals

The user-facing companion to the corpus's `access-transam` deep dive: LSNs,
segment files, full-page writes, and the write-ahead rule, in docs prose. Use
this for orientation; the per-file `xlog.c`/`xloginsert.c` docs for code.

## LSN — the byte-offset clock

- An **LSN (Log Sequence Number)** is a **byte offset into the WAL** that
  increases monotonically with every record; exposed as the **`pg_lsn`** type.
  Subtracting two LSNs gives WAL bytes between them — the unit replication lag
  and recovery progress are measured in. [from-docs]
  [verified-by-code, via [[knowledge/subsystems/access-transam.md]]]

## Segment files & pages

- WAL lives in **`pg_wal/`** as **segment files, normally 16 MB**, settable at
  `initdb` via **`--wal-segsize`**. Each segment is split into pages, normally
  **8 kB** (`XLOG_BLCKSZ`, set by the `--with-wal-blocksize` configure option). [from-docs]
- Segments get **ever-increasing 24-hex-digit names** starting
  `000000010000000000000001`; the counter **doesn't wrap** in any practical
  timeframe. [from-docs]
- Record header layout is in **`access/xlogrecord.h`**; record body depends on
  the rmgr/event. Records are appended by **`XLogInsert`**. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/xloginsert.c.md]]]

## The write-ahead rule + full-page writes

- **WAL describing a change must reach durable storage before the data page is
  modified on disk** — this is what makes crash recovery possible. A lying disk
  that caches writes while reporting success defeats it. [from-docs]
- **Full-page image (FPI):** with **`full_page_writes`** on (default), the
  **entire page is written to WAL on its first modification after a
  checkpoint**, so recovery can reconstruct a torn page (partial 8 kB write)
  from the WAL copy. This is why WAL volume spikes right after a checkpoint. [from-docs]
  [cross: knowledge/architecture/wal.md]

## Checkpoints, pg_control, recovery

- A checkpoint flushes dirty buffers and records its WAL position in
  **`pg_control`**. Recovery reads `pg_control` → the checkpoint record → then
  **REDOs forward** from the checkpoint's WAL location. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/xlog.c.md]]]
- `pg_control` is **smaller than one disk page**, so it's not subject to torn
  writes — a theoretical single point of failure that has not bitten in
  practice. [from-docs]
- Segments before the last checkpoint's needed WAL are **recycled** (renamed for
  future use) rather than deleted, avoiding constant create/unlink churn. [from-docs]

## Durability knobs (orientation)

- `fsync`, `wal_sync_method`, and placing `pg_wal/` on a separate disk (via a
  symlink) are the main durability/performance levers; details in
  `runtime-config-wal`. [from-docs]
  [cross: knowledge/docs-distilled/runtime-config-wal.md]

## Links into corpus
- [[knowledge/subsystems/access-transam.md]] — the WAL/xact subsystem synthesis (LSN, XLogInsert, redo).
- [[knowledge/architecture/wal.md]] — architecture-level WAL + crash-recovery narrative.
- [[knowledge/files/src/backend/access/transam/xlog.c.md]] — checkpoint, pg_control, recovery driver.
- [[knowledge/files/src/backend/access/transam/xloginsert.c.md]] — XLogInsert + FPI assembly.
- [[knowledge/docs-distilled/wal.md]] / [[knowledge/docs-distilled/runtime-config-wal.md]] — reliability + GUC companions.
- Skill: `wal-and-xlog` — adding/altering a WAL record, redo functions, FPI rules.

## Gaps / follow-ups
- The page is orientation-level; record-construction detail (XLogRegisterBuffer,
  REGBUF_* flags, registered-block FPI elision) lives only in the per-file docs +
  the `wal-and-xlog` skill — quote those for code-level claims.
