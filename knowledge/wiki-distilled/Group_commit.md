---
source_url: https://wiki.postgresql.org/wiki/Group_commit
fetched_at: 2026-06-03T19:50:00Z
wiki_last_edited: 2021-06-25
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: this is a stale 2012-era DESIGN PROPOSAL page (Simon Riggs / Peter
  Geoghegan, targeted at 9.2), not a description of shipped behavior. The
  *mechanism that actually shipped* is summarized from the docs + corpus below;
  read this page as history, not reference.
---

# Wiki distilled — Group commit

A design-proposal artifact, not a manual. Its real value is the framing of *why*
group commit matters; for what PG actually does today, see the corpus supplement.

## What the wiki page says (historical)

- **The goal:** batch many transactions' commits into a *single* WAL `fsync`,
  amortizing the most expensive part of `COMMIT` across concurrent sessions.
  [from-wiki]
- **It was a 9.2-era proposal** by Simon Riggs and Peter Geoghegan, designed to
  build on the synchronous-replication wait machinery, and pitched to *replace
  the older `commit_siblings` mechanism* — which the authors judged "ineffective
  and rarely used in practice." [from-wiki]
- The proposal anticipated being **on by default, possibly with no off switch**.
  [from-wiki]
- Benchmarking used Greg Smith's `pgbench` on ext4 (Linux 3.1) with a single
  7200-RPM SATA disk, write-caching on — i.e. the page is a point-in-time
  artifact, not current guidance. [from-wiki]
- The page is **light on mechanism**: no current GUC names beyond the obsolete
  `commit_siblings`, no `XLogFlush` detail, no leader/follower specifics. [from-wiki]

## Corpus supplement — what group commit actually is today

PG has effective group commit through two distinct, *already-shipped* paths:

- **Implicit ganged flush (the real, always-on group commit).** Because
  `XLogFlush` flushes WAL up to a requested LSN, a backend that wants to flush
  to LSN *X* will, on grabbing `WALWriteLock`, flush *everything* already in the
  buffers up to the current insert point — satisfying every other backend waiting
  for an LSN ≤ that point with one `fsync`. Under concurrency this batches commits
  automatically, no GUC required. [verified-by-code,
  source/src/backend/access/transam/xlog.c — `XLogFlush` at `xlog.c:2801`, via
  knowledge/files/src/backend/access/transam/xlog.c.md]
- **`commit_delay` / `commit_siblings` (the explicit, opt-in knob).** When
  `commit_delay > 0` and at least `commit_siblings` other transactions are
  active, the flushing leader sleeps `commit_delay` microseconds *inside*
  `XLogFlush` before issuing the `fsync`, deliberately widening the window so more
  followers join the same flush. It does nothing unless `fsync = on`. This is the
  mechanism the 2012 proposal called ineffective — it survived but as a niche
  tuning knob (default `commit_delay = 0`). [verified-by-code, xlog.c — commit_delay
  gang inside the flush path; see knowledge/docs-distilled/wal.md §WAL Configuration]
- **Distinct from asynchronous commit.** Group commit keeps commits *durable* —
  it just shares the fsync. Async commit (`synchronous_commit = off`) instead
  *defers* the flush and returns early, trading recent-txn durability. They are
  orthogonal: you can run both. [from-docs, knowledge/docs-distilled/wal.md §28.4]

## Why it matters operationally

- On a busy OLTP system the *implicit* ganged flush already gives most of the
  group-commit benefit for free; reach for `commit_delay` only when you have many
  short concurrent transactions bottlenecked on fsync latency and have measured
  that a few-microsecond leader delay raises throughput. On low-concurrency
  workloads `commit_delay` is pure added latency. [inferred, from-docs]
- The page's lasting lesson is the *shape of the problem* (fsync is the commit
  cost; concurrency is the lever), not any of its specific proposal details.
  [inferred]

## Links into corpus

- [[knowledge/files/src/backend/access/transam/xlog.c.md]] — `XLogFlush`
  (`xlog.c:2801`), the `commit_delay` gang, `WALWriteLock`-mediated shared flush.
- [[knowledge/files/src/backend/access/transam/xact.c.md]] —
  `RecordTransactionCommit` → `XLogFlush(XactLastRecEnd)`, the per-commit flush
  request that participates in the gang.
- [[knowledge/subsystems/access-transam.md]] — the WAL insert/flush subsystem.
- [[knowledge/docs-distilled/wal.md]] — §28.4 Async Commit and §28.5 WAL Config
  (`commit_delay`/`commit_siblings` defaults), the authoritative current-behavior
  companion to this historical page.
- Skill: `wal-and-xlog` — when editing the flush path in C.

## Confidence note

The wiki content is a 2012 design proposal, tagged `[from-wiki]` and explicitly
historical. Every current-behavior claim is `[verified-by-code]` against
`xlog.c` (last verified `ef6a95c7c64`; treated current per STATE.md anchor delta)
or `[from-docs]` against the WAL chapter. Treat the wiki page as archaeology.
</content>
