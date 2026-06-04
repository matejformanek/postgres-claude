---
source_url: https://www.postgresql.org/docs/current/wal.html
also_fetched:
  - https://www.postgresql.org/docs/current/wal-internals.html
  - https://www.postgresql.org/docs/current/wal-configuration.html
  - https://www.postgresql.org/docs/current/wal-async-commit.html
fetched_at: 2026-06-03T19:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 28/30: Reliability and the Write-Ahead Log

The "Reliability and the WAL" chapter. The index page (`wal.html`) carries no
substantive text; this run mines the three load-bearing sub-pages —
**WAL Internals**, **WAL Configuration**, and **Asynchronous Commit** — which is
where the non-obvious operational detail lives.

> Chapter-number note: the rendered docs label this Chapter 28; older trees
> numbered it 30. Section anchors (`wal-internals`, `wal-configuration`,
> `wal-async-commit`) are stable; cite by anchor, not number. [from-docs]

## Sub-section map

- **28.1 Reliability** — the disk-honesty problem (drives that lie about flush).
- **28.2 Data Checksums** (+ 28.2.1 off-line enabling).
- **28.3 Write-Ahead Logging (WAL)** — the WAL-before-data ordering rule.
- **28.4 Asynchronous Commit** — trade durability of *recent* txns for speed.
- **28.5 WAL Configuration** — checkpoint + flush + buffer GUCs.
- **28.6 WAL Internals** — on-disk layout, segments, LSN. [from-docs]

## Non-obvious claims — WAL Internals (28.6)

- **WAL lives in `pg_wal/`** under the data directory; performance trick is to
  put `pg_wal` on a *separate physical disk* via a symlink. [from-docs]
- **Segment files are 16 MB by default** (`--wal-segsize` at initdb time), named
  by a monotonically increasing hex sequence starting `000000010000000000000001`;
  the numbering **never wraps**. WAL pages within a segment are normally 8 kB
  (`--with-wal-blocksize` at configure time). [from-docs]
  [verified-by-code, source/src/backend/access/transam/xlog.c — segment lifecycle,
  via knowledge/files/src/backend/access/transam/xlog.c.md]
- **LSN (Log Sequence Number)** is a byte offset into the logical WAL stream,
  type **`pg_lsn`**, monotonically increasing. Subtracting two LSNs gives the
  *volume* of WAL between them — the unit replication/recovery progress is
  measured in. [from-docs]
- **The ordering invariant:** the WAL record describing a change must reach
  durable storage *before* the changed data page is allowed to. That single rule
  is what makes crash recovery a forward REDO scan from the last checkpoint.
  [from-docs]
- **Recovery is three steps:** read `pg_control` → read the checkpoint record it
  names → REDO forward from that checkpoint's LSN, replaying every record. All
  pages modified since the checkpoint are restored to a consistent state
  *provided `full_page_writes` was not disabled*. [from-docs]
- **`full_page_writes` defeats torn pages:** the first modification of a page
  after each checkpoint logs the *entire* page image, so a partial (torn) OS
  write during a crash is repaired by replaying the full image. This is why WAL
  volume spikes right after a checkpoint. [from-docs]
- WAL record header format is described in `access/xlogrecord.h`. [from-docs]

## Non-obvious claims — WAL Configuration (28.5)

| GUC | Default | Note |
|---|---|---|
| `checkpoint_timeout` | 5 min | max time between automatic checkpoints |
| `max_wal_size` | 1 GB | soft cap; checkpoint triggered before exceeding |
| `min_wal_size` | 80 MB | floor of recycled segments kept for reuse |
| `checkpoint_completion_target` | 0.9 | spread checkpoint I/O over this fraction of the interval |
| `checkpoint_flush_after` | 256 kB | force OS writeback after this much dirtied (Linux/POSIX) |
| `wal_buffers` | −1 | auto = 1/32 of `shared_buffers` |
| `full_page_writes` | on | see torn-page note above |
| `wal_sync_method` | platform-dependent | `fdatasync`/`fsync`/`open_datasync`/… |
| `commit_delay` | 0 µs | group-commit leader sleep inside `XLogFlush` |
| `commit_siblings` | 5 | min concurrent txns before `commit_delay` engages |

[from-docs — defaults cross-checked against guc_tables; treat unspecified ones
as [unverified] pending a guc_tables read]

- **Checkpoints are "fairly expensive":** they flush *all* dirty buffers + write
  a checkpoint record. Tuning toward *fewer, larger* checkpoints (raise
  `max_wal_size` / `checkpoint_timeout`) lowers steady-state cost but lengthens
  recovery and grows the post-checkpoint full-page-write spike. The two pressures
  pull opposite ways — that tension is the whole tuning story. [from-docs]
- **`commit_delay` only does anything when `fsync=on` AND at least
  `commit_siblings` other transactions are active** — otherwise the delay is pure
  latency with no batching payoff. It is a *synchronous* mechanism (see async
  note below). [from-docs]
- **Restartpoints** are the standby/archive-recovery analogue of checkpoints; a
  restartpoint can only happen at a replayed checkpoint record, so a standby can
  temporarily exceed `max_wal_size` by up to one checkpoint cycle. [from-docs]
- Newer knobs surfaced by this page: `recovery_prefetch` (default `try`),
  `wal_decode_buffer_size` (prefetch distance cap), `track_wal_io_timing`
  (feeds `XLogWrite`/`issue_xlog_fsync` timing into `pg_stat_io`),
  `wal_keep_size`. [from-docs]

## Non-obvious claims — Asynchronous Commit (28.4)

- **Async commit risks *lost recent transactions*, NOT corruption.** This is the
  single most important distinction on the page: with `synchronous_commit=off`
  the server acknowledges a commit before its WAL is flushed, so a crash can lose
  the last few committed txns — but recovery still replays WAL *in commit order*
  up to the last flushed record, so the database is always self-consistent. A txn
  B that depends on A can never survive while A is lost. [from-docs]
- **The risk window is bounded at `3 × wal_writer_delay`** — the WAL writer
  favors flushing whole pages during busy periods, so the worst-case unflushed
  span is three writer cycles, not unbounded. [from-docs]
- **`synchronous_commit` is per-transaction settable** and read *at commit time*;
  values: `on` (default), `off`, `local`, `remote_write`, `remote_apply` (the
  last three matter only with synchronous replication). [from-docs]
- **`fsync=off` is categorically more dangerous** than async commit: it disables
  PG's write-ordering entirely and risks *arbitrary corruption*. Async commit
  gives most of the throughput win without that exposure — reach for async commit
  first. [from-docs]
- **Some commands force a synchronous flush regardless** of the GUC: DDL like
  `DROP TABLE`, and two-phase `PREPARE TRANSACTION`. `commit_delay` is *ignored*
  for an asynchronously committing transaction. [from-docs]

## Links into corpus

- [[knowledge/architecture/wal.md]] — the PG-wide WAL concept doc this chapter
  underlies.
- [[knowledge/subsystems/access-transam.md]] — xlog.c / xact.c subsystem that
  implements WAL insert, flush, and the commit path.
- [[knowledge/files/src/backend/access/transam/xlog.c.md]] — `XLogFlush`
  (`xlog.c:2801`), `XLogWrite`, `commit_delay` group-commit gang, segment
  lifecycle. [verified-by-code]
- [[knowledge/files/src/backend/access/transam/xact.c.md]] —
  `RecordTransactionCommit` calls `XLogFlush(XactLastRecEnd)` (cited at
  xlog.c.md:308); the async path skips that flush.
- [[knowledge/files/src/backend/access/transam/xloginsert.c.md]] — record
  assembly feeding `XLogInsert`.
- [[knowledge/docs-distilled/storage.md]] — `pd_lsn` / `pd_checksum` page-header
  fields that interact with full-page writes and checksums.
- Skill: `wal-and-xlog` — code-edit checklist for adding/modifying WAL records.

## Gaps / follow-ups

- 28.1 Reliability and 28.2 Data Checksums (incl. off-line enabling via
  `pg_checksums`) were summarized only — each merits its own pass; seed
  `checksums` into the docs queue.
- GUC defaults marked above as cross-checked should be re-verified against
  `source/src/backend/utils/misc/guc_tables.c` in a file-backfill run; the docs
  page omitted several defaults (`wal_writer_delay`, `wal_compression`,
  `wal_level`, `wal_log_hints`, `wal_recycle`, `wal_init_zero`). [unverified]
</content>
</invoke>
