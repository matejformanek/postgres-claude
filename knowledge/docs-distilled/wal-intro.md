---
source_url: https://www.postgresql.org/docs/current/wal-intro.html
fetched_at: 2026-06-12T20:49:00Z
anchor_sha: e18b0cb
chapter: "30.3 Write-Ahead Logging (WAL)"
---

# Write-Ahead Logging (WAL) — intro (docs §30.3)

The one-paragraph "why WAL exists" page, distilled. `[from-docs]`.

## Non-obvious claims

- **The WAL invariant in one line:** a change to a data file (table or index)
  may be written to permanent storage only *after* the WAL record describing
  that change has been flushed. That ordering — log first, data later — is the
  whole mechanism. `[from-docs]`
- **WAL's payoff is that data pages need not be flushed on every commit.** A
  commit only has to flush the WAL; the dirty data pages can stay in shared
  buffers and be written lazily, because a crash can re-derive them by replaying
  (REDO-ing) WAL records that haven't yet reached the data files. `[from-docs]`
- **Disk-write reduction is structural, not incidental:** WAL is appended
  *sequentially*, so the fsync cost of the log is far below the cost of randomly
  flushing every data page a transaction touched — biggest win for many small
  transactions scattered across the heap. `[from-docs]`
- **One fsync can commit many transactions** — concurrent small commits batch
  into a single WAL flush. `[from-docs]`
- **WAL enables online backup + PITR:** replaying archived WAL over a *physical*
  base backup recovers to any instant in the archived range, and crucially the
  base backup need **not** be an instantaneous snapshot — replaying the WAL for
  the backup's duration repairs any internal inconsistency it captured.
  `[from-docs]`
- **Journaled filesystems become unnecessary for correctness** because WAL
  already restores consistency after a crash; the journaling overhead can often
  be dropped (e.g. `data=writeback` on ext3) for performance. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/wal.md]] — parent overview.
- [[knowledge/docs-distilled/wal-reliability.md]] — torn pages + full-page writes.
- [[knowledge/docs-distilled/wal-async-commit.md]] — relaxing the commit-flush wait.
- [[knowledge/subsystems/access-transam.md]] — XLogInsert/XLogFlush + checkpoint
  + the redo loop.
- Skill: `wal-and-xlog`.

## Citations

- All `[from-docs]`. REDO/checkpoint machinery lives in
  `source/src/backend/access/transam/xlog.c`. Verify at anchor e18b0cb.
