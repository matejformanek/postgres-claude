---
source_url: https://www.postgresql.org/docs/current/wal-reliability.html
fetched_at: 2026-06-12T20:48:00Z
anchor_sha: e18b0cb
chapter: "30.1 Reliability"
---

# Reliability (docs §30.1, WAL chapter)

The storage-stack reliability model behind WAL: caches, torn pages, full-page
writes, and exactly what is and isn't checksum-protected. `[from-docs]`.

## Non-obvious claims

- **Three cache layers sit between `fsync` and the platter**, each a durability
  hazard: OS buffer cache (PG forces flush via `wal_sync_method`), disk
  *controller* cache (write-back is unsafe unless a BBU holds power), and the
  drive's own cache (consumer SATA + many SSDs ship volatile write-back caches
  on by default). Making every layer honest is the admin's responsibility, not
  PG's. `[from-docs]`
- **Write barriers and BBUs fight each other.** A barrier-using FS (ext4, ZFS)
  issues `FLUSH CACHE EXT` / `SYNCHRONIZE CACHE`, which forces the *entire*
  controller cache to disk — defeating the whole point of the BBU. Fix is to
  disable FS barriers (only safe with a known-good battery) or reconfigure the
  controller; diagnose with `pg_test_fsync`. `[from-docs]`
- **Torn-page hazard is real at the 512-byte-sector level.** PG writes 8 kB
  pages = 16 sectors; a power loss mid-write leaves some sectors new, some old.
  **WAL full-page images are the defense:** the first modification of a page
  after each checkpoint logs the *entire* page image *before* the data file is
  touched, and recovery overwrites the possibly-torn page from WAL.
  `full_page_writes` (default on) governs this and may be turned off **only** on
  storage that can't tear an 8 kB write (e.g. ZFS). `[from-docs]`
- **A BBU does NOT by itself prevent partial page writes** — only if it
  guarantees data lands in the BBU as full 8 kB units. So `full_page_writes=off`
  on the strength of "I have a BBU" is unsafe. `[from-docs]`
- **Two distinct checksums, two scopes:** every WAL *record* carries a CRC-32C
  checked on crash/archive recovery and replication; data *pages* carry
  `data_checksums` (on by default in modern PG). Full-page images embedded in
  WAL are always checksum-protected. `[from-docs]`
- **A specific set of SLRU/auxiliary structures are NOT directly checksummed and
  NOT covered by full-page writes:** `pg_xact`, `pg_subtrans`, `pg_multixact`,
  `pg_serial`, `pg_notify`, `pg_stat`, `pg_snapshots`. They're rebuilt at
  recovery from their (CRC-32C-protected) WAL records instead. `pg_twophase`
  state files are individually CRC-32C-protected. `[from-docs]`
- **Temporary files have NO protection at all** — sorts, materializations, and
  large-query intermediates are neither checksummed nor WAL-logged. `[from-docs]`
- **ECC RAM is assumed, not provided.** PG explicitly does not defend against
  correctable memory errors. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/wal.md]] — parent WAL overview.
- [[knowledge/docs-distilled/wal-internals.md]] — record layout / CRC details.
- [[knowledge/subsystems/access-transam.md]] — XLOG insert/flush + checkpoint
  full-page-write triggering.
- [[knowledge/docs-distilled/storage-page-layout.md]] — the 8 kB page +
  per-page checksum field this protects.
- Skill: `wal-and-xlog` (full-page-image / FPI rules, MarkBufferDirtyHint).

## Citations

- All `[from-docs]`. Full-page-write logic lives in
  `source/src/backend/access/transam/xloginsert.c`; page checksum in
  `source/src/backend/storage/page/bufpage.c`. Verify at anchor e18b0cb.
