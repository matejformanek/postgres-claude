---
source_url: https://www.postgresql.org/docs/current/runtime-config-wal.html
fetched_at: 2026-06-04T18:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §20.5 Write Ahead Log configuration

The WAL GUC reference, distilled to the *surprising* semantics — the places
where a default or an interaction bites. Companion: `knowledge/architecture/wal.md`
for the mechanism, `knowledge/docs-distilled/wal.md` for the chapter overview.

## wal_level and durability

- **`wal_level` is cumulative: `minimal` < `replica` (default) < `logical`.** Each
  level logs everything the lower one does, plus more. `minimal` skips row-level
  logging for permanent-relation bulk ops (CREATE/REWRITE: CLUSTER, REINDEX,
  TRUNCATE, ALTER … SET TABLESPACE) — fast, but **breaks PITR and replication**.
  [from-docs]
- **`wal_level=minimal` + non-zero `max_wal_senders` = server won't start.** And
  switching to `minimal` invalidates prior base backups for PITR. [from-docs]
- **`fsync=off` is all-or-nothing and can corrupt.** When off, *no* `fsync()` is
  issued. Going off→on requires forcing kernel buffers to disk first
  (`initdb --sync-only`, `sync`, unmount, or reboot) — not optional. [from-docs]
- **`synchronous_commit=off` risks losing recent commits but never corrupts** —
  it is a durability *deadline*, not an integrity mechanism (the key contrast
  with `fsync`). The lost-commit window is capped at **3× `wal_writer_delay`**.
  [from-docs]
- **With empty `synchronous_standby_names`, only `on`/`off` are meaningful** —
  `remote_write`/`remote_apply`/`local` all degrade to local-flush `on` because
  there is no standby to coordinate with. [from-docs]

## Torn-page protection

- **`full_page_writes=on` (default) writes the whole 8 KiB page to WAL on the
  first modification after each checkpoint.** Row deltas can't reconstruct a
  half-old/half-new torn page; this is the guarantee that makes crash recovery
  correct. Turning it off risks silent corruption unless storage guarantees
  atomic sector writes. [from-docs]
- **`wal_log_hints=on` WAL-logs every hint-bit update as a full-page write**,
  even without data checksums — used to measure the FPI overhead checksums would
  add. Server-start-only. [from-docs] [cross-link
  knowledge/wiki-distilled/Hint_Bits.md]

## Group commit + WAL writer

- **`commit_delay` (µs, default `0`) + `commit_siblings` (default `5`)** form the
  explicit group-commit knob: the flush leader sleeps `commit_delay` if ≥
  `commit_siblings` other transactions are active; followers only wait for the
  leader's flush. Disabled when `fsync=off`. [from-docs] [cross-link
  knowledge/wiki-distilled/Group_commit.md — the implicit ganged XLogFlush]
- **`wal_buffers=-1` (default) = 1/32 of `shared_buffers`, clamped to
  [64 kB, 16 MB]** (one WAL segment). Values < 32 kB are bumped to 32 kB.
  [from-docs]
- **`wal_writer_delay` (default `200ms`) + `wal_writer_flush_after` (default
  `1MB`)**: between flushes, if less than the threshold of WAL is pending and
  less than the delay has elapsed, WAL is only *written* to the OS, not flushed.
  [from-docs]

## Checkpoints + WAL file lifecycle

- **`checkpoint_completion_target=0.9` (default) spreads checkpoint I/O over 90%
  of the inter-checkpoint interval** — lowering it makes I/O bursty (fast
  checkpoint then idle). [from-docs]
- **`checkpoint_flush_after` default `256kB` on Linux, `0` elsewhere** — forces
  OS writeback mid-checkpoint to avoid one giant fsync stall at the end.
  [from-docs]
- **`max_wal_size` (default `1GB`) is a *soft* limit** that triggers checkpoints;
  it can be exceeded under heavy load, a failing `archive_command`, or a high
  `wal_keep_size`. **`min_wal_size` (default `80MB`)**: below this, old segments
  are recycled rather than deleted. [from-docs]
- **`wal_recycle=on` (default) reuses segments by rename** — on COW filesystems
  this can be *slower* than fresh files; `wal_init_zero=on` (default) pre-zeroes
  new segments for space pre-allocation, also skippable on COW. [from-docs]

## Archiving + recovery

- **`archive_command` and `archive_library` are mutually exclusive** (error if
  both non-empty). With `archive_mode=on` and an empty `archive_command`, WAL
  *accumulates* waiting — it's a pause, not a disable. [from-docs]
- **`archive_timeout` forces a segment switch on idle clusters, but only if
  there is activity**; early-switched segments are still full 16 MB, so tiny
  timeouts bloat the archive. [from-docs]
- **`recovery_prefetch=try` (default)** prefetches blocks referenced in WAL
  during recovery, bounded by `wal_decode_buffer_size` (default `512kB`,
  start-only). [from-docs]

## WAL summarization (incremental backup)

- **`summarize_wal=on` requires `wal_level` > `minimal`**; the summarizer runs
  but refuses to emit summaries under `minimal`. **`wal_summary_keep_time`
  (default `10 days`, start-only)** auto-deletes old summaries; `0` = keep
  forever. A summary gap between a base and the next incremental backup makes the
  incremental fail. [from-docs]

## Links into corpus

- [[knowledge/architecture/wal.md]] — the WAL mechanism these GUCs tune.
- [[knowledge/docs-distilled/wal.md]] — the WAL chapter overview.
- [[knowledge/subsystems/access-transam.md]] — XLogInsert/XLogFlush internals.
- [[knowledge/wiki-distilled/Group_commit.md]] — `commit_delay`/`commit_siblings`
  and the implicit ganged flush.
- [[knowledge/wiki-distilled/Hint_Bits.md]] — `wal_log_hints` / FPI interaction.
- [[knowledge/docs-distilled/runtime-config-replication.md]] — `max_wal_senders`
  / `wal_keep_size` cross-dependencies named here.
- Skill: `wal-and-xlog` — emitting/replaying WAL records in C.

## Confidence note

All claims `[from-docs]` (§20.5, fetched 2026-06-04). Defaults quoted as on the
page; not re-verified against `guc_tables.c` this run (a future
pg-quality-auditor pass could pin each default to a source line).
</content>
